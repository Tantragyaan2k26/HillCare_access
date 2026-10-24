"""Joint-Embedding Predictive Architecture (I-JEPA) for Earth Observation (v1.1).

Implements self-supervised multi-modal Vision Transformer encoder for Sentinel-1 SAR
and Sentinel-2 optical scenes over Himalayan terrain, with downstream heads for
trails, settlements, and landslide feature extraction.
"""

from __future__ import annotations

import torch
from torch import nn


class PatchEmbed(nn.Module):
    """Split 2D satellite tile into patches and project into embedding dimension."""
    def __init__(
        self,
        img_size: int = 64,
        patch_size: int = 8,
        in_chans: int = 4,  # Sentinel-2 (RGB+NIR) or S1 (VV/VH + DEM)
        embed_dim: int = 128,
    ):
        super().__init__()
        self.img_size = img_size
        self.patch_size = patch_size
        self.num_patches = (img_size // patch_size) ** 2
        self.proj = nn.Conv2d(in_chans, embed_dim, kernel_size=patch_size, stride=patch_size)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, C, H, W) -> (B, num_patches, embed_dim)
        x = self.proj(x)
        x = x.flatten(2).transpose(1, 2)
        return x


class TransformerBlock(nn.Module):
    """Standard multi-head self-attention transformer block."""
    def __init__(self, dim: int = 128, num_heads: int = 4, mlp_ratio: float = 4.0):
        super().__init__()
        self.norm1 = nn.LayerNorm(dim)
        self.attn = nn.MultiheadAttention(embed_dim=dim, num_heads=num_heads, batch_first=True)
        self.norm2 = nn.LayerNorm(dim)
        mlp_hidden_dim = int(dim * mlp_ratio)
        self.mlp = nn.Sequential(
            nn.Linear(dim, mlp_hidden_dim),
            nn.GELU(),
            nn.Linear(mlp_hidden_dim, dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        norm_x = self.norm1(x)
        attn_out, _ = self.attn(norm_x, norm_x, norm_x)
        x = x + attn_out
        x = x + self.mlp(self.norm2(x))
        return x


class HimalayanJEPAEncoder(nn.Module):
    """Context and Target Encoder for Earth-Observation I-JEPA."""
    def __init__(
        self,
        img_size: int = 64,
        patch_size: int = 8,
        in_chans: int = 4,
        embed_dim: int = 128,
        depth: int = 4,
        num_heads: int = 4,
    ):
        super().__init__()
        self.patch_embed = PatchEmbed(img_size, patch_size, in_chans, embed_dim)
        num_patches = self.patch_embed.num_patches
        self.pos_embed = nn.Parameter(torch.zeros(1, num_patches, embed_dim))
        self.blocks = nn.ModuleList([
            TransformerBlock(embed_dim, num_heads) for _ in range(depth)
        ])
        self.norm = nn.LayerNorm(embed_dim)
        nn.init.trunc_normal_(self.pos_embed, std=0.02)

    def forward(self, x: torch.Tensor, mask_indices: torch.Tensor | None = None) -> torch.Tensor:
        """Encode visible context patches into latent space."""
        x = self.patch_embed(x)
        x = x + self.pos_embed

        if mask_indices is not None:
            # Gather unmasked context patches
            _, _, D = x.shape
            x = torch.gather(x, dim=1, index=mask_indices.unsqueeze(-1).expand(-1, -1, D))

        for block in self.blocks:
            x = block(x)
        return self.norm(x)


class DownstreamTrailHead(nn.Module):
    """Downstream segmentation head on frozen JEPA representations for trails and footpaths."""
    def __init__(self, embed_dim: int = 128, out_chans: int = 1):
        super().__init__()
        self.head = nn.Sequential(
            nn.Linear(embed_dim, 64),
            nn.ReLU(),
            nn.Linear(64, out_chans),
            nn.Sigmoid(),
        )

    def forward(self, latent_embeddings: torch.Tensor) -> torch.Tensor:
        # returns trail probability per patch
        return self.head(latent_embeddings)


class DownstreamLandslideHead(nn.Module):
    """Downstream classification head for landslide and slope movement detection."""
    def __init__(self, embed_dim: int = 128):
        super().__init__()
        self.head = nn.Sequential(
            nn.Linear(embed_dim, 64),
            nn.ReLU(),
            nn.Linear(64, 2),  # [stable, hazard]
        )

    def forward(self, latent_embeddings: torch.Tensor) -> torch.Tensor:
        # pool over patches -> (B, embed_dim)
        pooled = latent_embeddings.mean(dim=1)
        return self.head(pooled)
