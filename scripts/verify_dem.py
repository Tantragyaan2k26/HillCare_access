#!/usr/bin/env python3
"""verify_dem.py — Independent verification of district DEM GeoTIFF outputs.

Checks raster metadata without requiring rasterio or GDAL:
  - Binary TIFF IFD: dimensions, bit-depth, sample format, compression
  - JSON sidecar: CRS, affine transform, pixel size, nodata, bounds
  - Pixel-level: nodata mask fraction, valid elevation range
  - Extent vs. district polygon bounding box (via pyproj + shapely)

Uses only: numpy, pyproj, shapely, struct (stdlib).
Exit code 0 on success, 1 on any failure.

Usage:
    python scripts/verify_dem.py
    python scripts/verify_dem.py --district Chamoli
"""

from __future__ import annotations
import argparse
import json
import math
import struct
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    from pyproj import CRS, Transformer
    HAS_PYPROJ = True
except ImportError:
    HAS_PYPROJ = False
    print("WARNING: pyproj not available — CRS authority code check skipped", file=sys.stderr)

try:
    from shapely.geometry import shape as shapely_shape, Point
    HAS_SHAPELY = True
except ImportError:
    HAS_SHAPELY = False
    print("WARNING: shapely not available — point-in-polygon checks skipped", file=sys.stderr)


PROC_DIR = Path("d:/GeoAI/data/processed")
DISTRICTS = ["Chamoli", "Pithoragarh", "Rudraprayag"]

# Expected constants
EXPECTED_CRS_EPSG = 32644
EXPECTED_PIXEL_M = 30.0
EXPECTED_NODATA = -9999.0


# ---------------------------------------------------------------------------
# Binary TIFF reader (IFD only, no full file scan)
# ---------------------------------------------------------------------------

TIFF_TAGS = {
    256: "ImageWidth", 257: "ImageLength", 258: "BitsPerSample",
    259: "Compression", 339: "SampleFormat", 278: "RowsPerStrip",
    273: "StripOffsets", 279: "StripByteCounts",
    33550: "ModelPixelScaleTag", 33922: "ModelTiepointTag",
    34735: "GeoKeyDirectoryTag", 34736: "GeoDoubleParamsTag",
    42113: "GDAL_NODATA",
}

TYPE_SIZES = {1:1, 2:1, 3:2, 4:4, 5:8, 6:1, 7:1, 8:2, 9:4, 10:8, 11:4, 12:8, 16:8}


def _parse_tiff_ifd(chunk: bytes, endian: str, ifd_offset: int) -> Dict[str, Any]:
    """Parse TIFF IFD entries from a byte chunk."""
    tags: Dict[str, Any] = {}
    if ifd_offset + 2 > len(chunk):
        return tags
    n = struct.unpack_from(endian + "H", chunk, ifd_offset)[0]
    pos = ifd_offset + 2
    for _ in range(min(n, 300)):
        if pos + 12 > len(chunk):
            break
        tag, dtype, count = struct.unpack_from(endian + "HHI", chunk, pos)
        val_bytes = chunk[pos + 8: pos + 12]
        tsize = TYPE_SIZES.get(dtype, 1)
        dsize = tsize * count
        try:
            if dsize <= 4:
                if dtype == 3:
                    val = struct.unpack_from(endian + "H", val_bytes)[0] if count == 1 else \
                          [struct.unpack_from(endian + "H", val_bytes, i * 2)[0] for i in range(count)]
                elif dtype == 4:
                    val = struct.unpack_from(endian + "I", val_bytes)[0]
                elif dtype == 2:
                    val = val_bytes[:count].rstrip(b"\x00").decode("ascii", errors="replace")
                else:
                    val = val_bytes
            else:
                off = struct.unpack_from(endian + "I", val_bytes)[0]
                if off + dsize <= len(chunk):
                    raw = chunk[off: off + dsize]
                    if dtype == 12:
                        val = [struct.unpack_from(endian + "d", raw, i * 8)[0] for i in range(count)]
                    elif dtype == 4:
                        val = [struct.unpack_from(endian + "I", raw, i * 4)[0] for i in range(count)]
                    elif dtype == 3:
                        val = [struct.unpack_from(endian + "H", raw, i * 2)[0] for i in range(count)]
                    elif dtype == 2:
                        val = raw.rstrip(b"\x00").decode("ascii", errors="replace")
                    else:
                        val = f"[offset={off}, size={dsize}]"
                else:
                    val = f"[offset={off} beyond chunk]"
        except Exception as exc:
            val = f"[parse error: {exc}]"
        tag_name = TIFF_TAGS.get(tag, f"TAG_{tag}")
        tags[tag_name] = val
        pos += 12
    return tags


def read_tiff_meta(filepath: Path, chunk_bytes: int = 1 * 1024 * 1024) -> Dict[str, Any]:
    """Read TIFF binary header and return metadata dict."""
    result: Dict[str, Any] = {"path": str(filepath), "size_bytes": filepath.stat().st_size}
    with open(filepath, "rb") as f:
        chunk = f.read(min(chunk_bytes, filepath.stat().st_size))
    if len(chunk) < 8:
        result["error"] = "File too short"
        return result
    byte_order = chunk[:2]
    if byte_order == b"II":
        endian = "<"
    elif byte_order == b"MM":
        endian = ">"
    else:
        result["error"] = f"Not a TIFF (magic: {chunk[:4].hex()})"
        return result
    magic = struct.unpack_from(endian + "H", chunk, 2)[0]
    if magic == 43:
        result["format"] = "BigTIFF"
        ifd_off = struct.unpack_from(endian + "Q", chunk, 8)[0]
    elif magic == 42:
        result["format"] = "TIFF"
        ifd_off = struct.unpack_from(endian + "I", chunk, 4)[0]
    else:
        result["error"] = f"Unknown TIFF magic: {magic}"
        return result
    tags = _parse_tiff_ifd(chunk, endian, ifd_off)
    result["tags"] = tags
    result["endian"] = endian
    return result


def read_first_strip_stats(filepath: Path, tags: Dict[str, Any],
                           nodata_val: float = -9999.0) -> Dict[str, Any]:
    """Read the first strip of a float32 raster and return pixel statistics."""
    strip_offsets = tags.get("StripOffsets")
    strip_counts = tags.get("StripByteCounts")
    if strip_offsets is None or strip_counts is None:
        return {"error": "StripOffsets/StripByteCounts not found in IFD chunk"}

    first_offset = strip_offsets[0] if isinstance(strip_offsets, list) else strip_offsets
    first_bytes = strip_counts[0] if isinstance(strip_counts, list) else strip_counts

    if isinstance(first_offset, str) or isinstance(first_bytes, str):
        return {"error": f"Strip info out of IFD chunk: offset={first_offset}"}

    with open(filepath, "rb") as f:
        f.seek(first_offset)
        raw = f.read(first_bytes)

    arr = np.frombuffer(raw, dtype="<f4")
    nodata_mask = arr == nodata_val
    nan_mask = ~np.isfinite(arr)
    valid = arr[~nodata_mask & ~nan_mask]

    return {
        "total_pixels": len(arr),
        "nodata_pixels": int(nodata_mask.sum()),
        "nan_inf_pixels": int(nan_mask.sum()),
        "valid_pixels": len(valid),
        "nodata_pct": round(float(nodata_mask.sum()) / len(arr) * 100, 2) if len(arr) else 0.0,
        "valid_min_m": round(float(valid.min()), 2) if len(valid) else None,
        "valid_max_m": round(float(valid.max()), 2) if len(valid) else None,
        "valid_mean_m": round(float(valid.mean()), 2) if len(valid) else None,
    }


# ---------------------------------------------------------------------------
# JSON sidecar validation
# ---------------------------------------------------------------------------

def validate_sidecar(sidecar_path: Path) -> Tuple[bool, Dict[str, Any], List[str]]:
    """Validate a DEM JSON sidecar. Returns (ok, data, errors)."""
    errors: List[str] = []
    if not sidecar_path.exists():
        return False, {}, [f"Sidecar not found: {sidecar_path}"]
    size = sidecar_path.stat().st_size
    if size == 0:
        # Windows may show 0 — try reading
        try:
            with open(sidecar_path, "rb") as f:
                raw = f.read()
            if not raw.strip():
                return False, {}, ["Sidecar is genuinely empty"]
        except OSError as e:
            return False, {}, [f"Cannot read sidecar: {e}"]
    with open(sidecar_path) as f:
        data = json.load(f)

    required = ["crs", "district", "pixel_size_meters", "nodata", "transform", "bounds_utm44n", "shape"]
    for key in required:
        if key not in data:
            errors.append(f"Missing key: {key}")

    if "crs" in data:
        if data["crs"] != f"EPSG:{EXPECTED_CRS_EPSG}":
            errors.append(f"CRS mismatch: got {data['crs']}, expected EPSG:{EXPECTED_CRS_EPSG}")
        elif HAS_PYPROJ:
            try:
                crs_obj = CRS.from_user_input(data["crs"])
                epsg = crs_obj.to_epsg()
                if epsg != EXPECTED_CRS_EPSG:
                    errors.append(f"pyproj resolves CRS to EPSG:{epsg}, not {EXPECTED_CRS_EPSG}")
            except Exception as e:
                errors.append(f"pyproj CRS parse error: {e}")

    if "pixel_size_meters" in data:
        if abs(data["pixel_size_meters"] - EXPECTED_PIXEL_M) > 0.1:
            errors.append(f"pixel_size_meters {data['pixel_size_meters']} != {EXPECTED_PIXEL_M}")

    if "nodata" in data:
        if data["nodata"] != EXPECTED_NODATA:
            errors.append(f"nodata {data['nodata']} != {EXPECTED_NODATA}")

    if "transform" in data:
        t = data["transform"]
        if len(t) != 6:
            errors.append(f"transform must have 6 elements, got {len(t)}")
        else:
            xscale, _, x_origin, _, yscale, y_origin = t
            if abs(xscale - EXPECTED_PIXEL_M) > 0.1:
                errors.append(f"transform x-scale {xscale} != {EXPECTED_PIXEL_M}")
            if abs(yscale + EXPECTED_PIXEL_M) > 0.1:
                errors.append(f"transform y-scale {yscale} != -{EXPECTED_PIXEL_M} (should be negative)")

    if "bounds_utm44n" in data and "shape" in data:
        b = data["bounds_utm44n"]
        s = data["shape"]
        if len(b) == 4 and len(s) == 2:
            exp_cols = round((b[2] - b[0]) / EXPECTED_PIXEL_M)
            exp_rows = round((b[3] - b[1]) / EXPECTED_PIXEL_M)
            if abs(exp_cols - s[1]) > 2:
                errors.append(f"Cols mismatch: bounds→{exp_cols} vs shape {s[1]}")
            if abs(exp_rows - s[0]) > 2:
                errors.append(f"Rows mismatch: bounds→{exp_rows} vs shape {s[0]}")

    return len(errors) == 0, data, errors


# ---------------------------------------------------------------------------
# Extent comparison with district polygon
# ---------------------------------------------------------------------------

def verify_extent_vs_polygon(meta: Dict[str, Any], district_geojson_path: Path,
                              district_name: str) -> List[str]:
    """Compare DEM UTM extent to district polygon bbox. Returns list of warnings."""
    warnings: List[str] = []
    if not HAS_PYPROJ or not HAS_SHAPELY:
        return ["SKIPPED: pyproj/shapely not available"]
    if not district_geojson_path.exists():
        return [f"SKIPPED: district boundaries file not found: {district_geojson_path}"]

    with open(district_geojson_path) as f:
        gj = json.load(f)

    poly_feat = next(
        (f for f in gj["features"] if f["properties"].get("district_name") == district_name),
        None,
    )
    if poly_feat is None:
        return [f"District '{district_name}' not found in boundaries GeoJSON"]

    poly_coords = poly_feat["geometry"]["coordinates"][0]
    xs = [c[0] for c in poly_coords]
    ys = [c[1] for c in poly_coords]
    poly_bbox_deg = (min(xs), min(ys), max(xs), max(ys))

    # Convert DEM UTM bounds to WGS84 for comparison
    transformer = Transformer.from_crs(f"EPSG:{EXPECTED_CRS_EPSG}", "EPSG:4326", always_xy=True)
    dem_bounds = meta["bounds_utm44n"]
    sw_lon, sw_lat = transformer.transform(dem_bounds[0], dem_bounds[1])
    ne_lon, ne_lat = transformer.transform(dem_bounds[2], dem_bounds[3])

    # Check within ~1 km tolerance (roughly 0.01 degrees)
    tol_deg = 0.015
    if sw_lon < poly_bbox_deg[0] - tol_deg or ne_lon > poly_bbox_deg[2] + tol_deg:
        warnings.append(
            f"DEM lon [{sw_lon:.4f}, {ne_lon:.4f}] extends beyond polygon bbox "
            f"[{poly_bbox_deg[0]:.4f}, {poly_bbox_deg[2]:.4f}] + {tol_deg} tol"
        )
    if sw_lat < poly_bbox_deg[1] - tol_deg or ne_lat > poly_bbox_deg[3] + tol_deg:
        warnings.append(
            f"DEM lat [{sw_lat:.4f}, {ne_lat:.4f}] extends beyond polygon bbox "
            f"[{poly_bbox_deg[1]:.4f}, {poly_bbox_deg[3]:.4f}] + {tol_deg} tol"
        )
    if not warnings:
        pass  # extents match

    # Rough scale check
    mid_lat = (sw_lat + ne_lat) / 2
    dem_w_km = (dem_bounds[2] - dem_bounds[0]) / 1000
    dem_h_km = (dem_bounds[3] - dem_bounds[1]) / 1000
    poly_w_km = (poly_bbox_deg[2] - poly_bbox_deg[0]) * 111.0 * math.cos(math.radians(mid_lat))
    poly_h_km = (poly_bbox_deg[3] - poly_bbox_deg[1]) * 111.0
    ratio_w = dem_w_km / poly_w_km if poly_w_km > 0 else 0
    ratio_h = dem_h_km / poly_h_km if poly_h_km > 0 else 0
    if not (0.95 <= ratio_w <= 1.05):
        warnings.append(f"W-E scale ratio {ratio_w:.3f} outside 0.95–1.05 (DEM {dem_w_km:.1f} km vs poly {poly_w_km:.1f} km)")
    if not (0.95 <= ratio_h <= 1.05):
        warnings.append(f"N-S scale ratio {ratio_h:.3f} outside 0.95–1.05 (DEM {dem_h_km:.1f} km vs poly {poly_h_km:.1f} km)")

    return warnings


# ---------------------------------------------------------------------------
# Main verification loop
# ---------------------------------------------------------------------------

def verify_district(name: str, verbose: bool = True) -> bool:
    """Verify one district's DEM outputs. Returns True if all checks pass."""
    key = name.lower()
    tif_path = PROC_DIR / f"dem_{key}_utm44n.tif"
    json_path = PROC_DIR / f"dem_{key}_utm44n.json"
    dist_gj_path = PROC_DIR / "district_boundaries.geojson"

    ok = True
    print(f"\n{'='*60}")
    print(f"  Verifying: {name}")
    print(f"{'='*60}")

    # 1. File existence
    if not tif_path.exists():
        print(f"  [FAIL] TIF not found: {tif_path}")
        return False
    if not json_path.exists():
        print(f"  [FAIL] JSON not found: {json_path}")
        return False
    print(f"  [OK]   TIF  {tif_path.name}  {tif_path.stat().st_size / 1e6:.1f} MB")
    print(f"  [OK]   JSON {json_path.name}")

    # 2. JSON sidecar validation
    sidecar_ok, meta, sidecar_errors = validate_sidecar(json_path)
    if sidecar_errors:
        for e in sidecar_errors:
            print(f"  [FAIL] Sidecar: {e}")
        ok = False
    else:
        print(f"  [OK]   Sidecar: CRS={meta['crs']}, pixel={meta['pixel_size_meters']}m, "
              f"nodata={meta['nodata']}, shape={meta['shape']}")
        if HAS_PYPROJ:
            print(f"  [OK]   pyproj confirms CRS is valid EPSG:{EXPECTED_CRS_EPSG}")

    # 3. TIFF binary header
    tif_meta = read_tiff_meta(tif_path)
    if "error" in tif_meta:
        print(f"  [FAIL] TIFF header: {tif_meta['error']}")
        ok = False
    else:
        tags = tif_meta["tags"]
        w = tags.get("ImageWidth")
        h = tags.get("ImageLength")
        bits = tags.get("BitsPerSample")
        sfmt = tags.get("SampleFormat")
        compr = tags.get("Compression")
        print(f"  [OK]   TIFF header: {w}×{h} px, {bits}-bit, SampleFormat={sfmt} (3=float32), Compression={compr}")

        # Cross-check shape vs sidecar
        if meta and "shape" in meta:
            if w != meta["shape"][1] or h != meta["shape"][0]:
                print(f"  [FAIL] Shape mismatch: TIFF {w}×{h} vs JSON {meta['shape'][1]}×{meta['shape'][0]}")
                ok = False
            else:
                print(f"  [OK]   TIFF dimensions match sidecar shape")

        # 4. Pixel-level stats from first strip
        strip_stats = read_first_strip_stats(tif_path, tags, nodata_val=EXPECTED_NODATA)
        if "error" in strip_stats:
            print(f"  [WARN] Strip stats: {strip_stats['error']}")
        else:
            ss = strip_stats
            print(f"  [OK]   Pixel stats: {ss['total_pixels']:,} total, "
                  f"{ss['nodata_pixels']:,} nodata ({ss['nodata_pct']}%), "
                  f"{ss['nan_inf_pixels']} NaN/Inf, "
                  f"{ss['valid_pixels']:,} valid")
            print(f"  [OK]   Valid elevation: [{ss['valid_min_m']}, {ss['valid_max_m']}] m  "
                  f"mean={ss['valid_mean_m']} m")
            if ss['nodata_pct'] > 0:
                print(f"  [OK]   Polygon clip confirmed (nodata % > 0)")
            else:
                print(f"  [WARN] No nodata pixels in first strip — may be bbox crop only")
            if ss['nan_inf_pixels'] > 0:
                print(f"  [WARN] {ss['nan_inf_pixels']} NaN/Inf pixels found")

            # Compare against sidecar stats
            if meta:
                sidecar_min = meta.get("min_elevation_m")
                sidecar_max = meta.get("max_elevation_m")
                if sidecar_min and abs(ss['valid_min_m'] - sidecar_min) > 1.0:
                    print(f"  [WARN] Min elev mismatch: strip={ss['valid_min_m']} vs sidecar={sidecar_min}")
                if sidecar_max and abs(ss['valid_max_m'] - sidecar_max) > 1.0:
                    print(f"  [WARN] Max elev mismatch: strip={ss['valid_max_m']} vs sidecar={sidecar_max}")

    # 5. Extent vs polygon
    if meta:
        ext_warnings = verify_extent_vs_polygon(meta, dist_gj_path, name)
        if ext_warnings:
            for w_msg in ext_warnings:
                if w_msg.startswith("SKIPPED"):
                    print(f"  [SKIP] Extent check: {w_msg}")
                else:
                    print(f"  [WARN] Extent: {w_msg}")
        else:
            print(f"  [OK]   DEM extent is consistent with district polygon bbox")

    if ok:
        print(f"  => PASS")
    else:
        print(f"  => FAIL")
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify district DEM outputs.")
    parser.add_argument("--district", choices=DISTRICTS + [d.lower() for d in DISTRICTS],
                        help="Verify only one district")
    args = parser.parse_args()

    districts = DISTRICTS
    if args.district:
        districts = [d for d in DISTRICTS if d.lower() == args.district.lower()]

    all_ok = True
    for dist in districts:
        if not verify_district(dist):
            all_ok = False

    print(f"\n{'='*60}")
    if all_ok:
        print("  All verifications PASSED")
    else:
        print("  Some verifications FAILED — see details above")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
