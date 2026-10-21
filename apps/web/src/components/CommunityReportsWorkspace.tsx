import React, { FormEvent, useState } from 'react';
import { fetchCommunityReports, fetchCommunityReportStatus, reviewCommunityReport, submitCommunityReport } from '../services/api';
import { CommunityCategory, CommunityReportReceipt, CommunityReportReview, CommunityStatus } from '../types';
import { RealDataExplorer } from './RealDataExplorer';

interface CommunityReportsWorkspaceProps {
  district: string;
}

const categories: Array<{ value: CommunityCategory; label: string }> = [
  { value: 'missing_habitation', label: 'Missing habitation' },
  { value: 'missing_facility', label: 'Missing healthcare facility' },
  { value: 'road_update', label: 'Road update' },
  { value: 'correction', label: 'Correction to a source feature' },
  { value: 'facility_closure', label: 'Facility closure or status change' },
  { value: 'access_barrier', label: 'Access barrier' },
];

const statuses: CommunityStatus[] = [
  'pending',
  'community-confirmed',
  'officially-confirmed',
  'rejected',
  'needs-recheck',
];

export const CommunityReportsWorkspace: React.FC<CommunityReportsWorkspaceProps> = ({ district }) => {
  const [category, setCategory] = useState<CommunityCategory>('missing_habitation');
  const [latitude, setLatitude] = useState('');
  const [longitude, setLongitude] = useState('');
  const [subject, setSubject] = useState('');
  const [description, setDescription] = useState('');
  const [evidenceSource, setEvidenceSource] = useState('');
  const [evidenceUrl, setEvidenceUrl] = useState('');
  const [observedOn, setObservedOn] = useState('');
  const [basedOnReportId, setBasedOnReportId] = useState('');
  const [pickMode, setPickMode] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [receipt, setReceipt] = useState<CommunityReportReceipt | null>(null);
  const [lookupId, setLookupId] = useState('');
  const [lookupResult, setLookupResult] = useState<CommunityReportReceipt | null>(null);
  const [reviewerToken, setReviewerToken] = useState('');
  const [reviewQueue, setReviewQueue] = useState<CommunityReportReview[]>([]);
  const [reviewNote, setReviewNote] = useState('');
  const [reviewStatus, setReviewStatus] = useState<CommunityStatus>('needs-recheck');
  const [reviewError, setReviewError] = useState('');

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true);
    setError('');
    setReceipt(null);
    try {
      const created = await submitCommunityReport({
        category,
        district,
        latitude: Number(latitude),
        longitude: Number(longitude),
        subject,
        description,
        evidence_source: evidenceSource,
        ...(evidenceUrl ? { evidence_url: evidenceUrl } : {}),
        ...(observedOn ? { observed_on: observedOn } : {}),
        ...(basedOnReportId ? { based_on_report_id: basedOnReportId } : {}),
      });
      setReceipt(created);
      setSubject('');
      setDescription('');
      setEvidenceSource('');
      setEvidenceUrl('');
      setObservedOn('');
      setBasedOnReportId('');
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Submission failed.');
    } finally {
      setBusy(false);
    }
  };

  const lookup = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setReviewError('');
    try {
      setLookupResult(await fetchCommunityReportStatus(lookupId.trim()));
    } catch (reason) {
      setReviewError(reason instanceof Error ? reason.message : 'Could not look up that report.');
      setLookupResult(null);
    }
  };

  const loadQueue = async () => {
    setReviewError('');
    try {
      setReviewQueue(await fetchCommunityReports(reviewerToken));
    } catch (reason) {
      setReviewError(reason instanceof Error ? reason.message : 'Could not access reviewer queue.');
    }
  };

  const review = async (report: CommunityReportReview) => {
    setReviewError('');
    try {
      await reviewCommunityReport(report.id, reviewerToken, reviewStatus, reviewNote);
      setReviewNote('');
      await loadQueue();
    } catch (reason) {
      setReviewError(reason instanceof Error ? reason.message : 'Review update failed.');
    }
  };

  return (
    <main className="community-page">
      <header className="community-header">
        <p className="real-eyebrow">COMMUNITY CONTRIBUTIONS · REVIEW REQUIRED</p>
        <h1>Suggest an update</h1>
        <p>Reports are stored separately from published source data and stay pending until an authorized reviewer verifies them.</p>
      </header>

      <section className="community-form-layout">
        <form className="community-form" onSubmit={submit}>
          <label>Report type
            <select value={category} onChange={(event) => setCategory(event.target.value as CommunityCategory)}>
              {categories.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
            </select>
          </label>
          <label>District
            <select value={district} disabled>
              <option>{district}</option>
            </select>
          </label>
          <div className="community-coordinate-grid">
            <label>Latitude
              <input type="number" min="6" max="38" step="any" required value={latitude} onChange={(event) => setLatitude(event.target.value)} />
            </label>
            <label>Longitude
              <input type="number" min="68" max="98" step="any" required value={longitude} onChange={(event) => setLongitude(event.target.value)} />
            </label>
          </div>
          <button type="button" className="real-tool-button" onClick={() => setPickMode((current) => !current)}>
            {pickMode ? 'Cancel map selection' : 'Choose coordinates on map'}
          </button>
          <label>Short title
            <input minLength={3} maxLength={160} required value={subject} onChange={(event) => setSubject(event.target.value)} />
          </label>
          <label>What did you observe?
            <textarea minLength={10} maxLength={4000} required rows={4} value={description} onChange={(event) => setDescription(event.target.value)} />
          </label>
          <label>Evidence source or reference
            <input minLength={3} maxLength={240} required value={evidenceSource} onChange={(event) => setEvidenceSource(event.target.value)} placeholder="For example: district notice, field visit, OSM note" />
          </label>
          <label>Evidence URL (optional)
            <input type="url" value={evidenceUrl} onChange={(event) => setEvidenceUrl(event.target.value)} placeholder="https://" />
          </label>
          <label>Date observed (optional)
            <input type="date" value={observedOn} onChange={(event) => setObservedOn(event.target.value)} />
          </label>
          {category === 'correction' && <label>Related report ID (optional)
            <input value={basedOnReportId} onChange={(event) => setBasedOnReportId(event.target.value)} />
          </label>}
          <button className="community-submit" type="submit" disabled={busy}>{busy ? 'Submitting…' : 'Submit for review'}</button>
          {error && <p role="alert" className="community-error">{error}</p>}
          {receipt && <div className="community-receipt" role="status">
            <b>Saved · pending review</b>
            <span>Report ID: {receipt.id}</span>
            <span>Submission time: {new Date(receipt.submitted_at).toLocaleString()}</span>
            <span>Published data was not changed.</span>
          </div>}
          <p className="community-privacy">This form does not ask for or publish a name, email, phone number, or other personal information. Do not include personal information in evidence notes.</p>
        </form>

        <div className="community-map-picker">
          <h2>Coordinate picker</h2>
          <p>Choose coordinates on the source-feature map. A selected position is an approximate report location, not an added/verified feature.</p>
          <RealDataExplorer
            district={district}
            coordinatePickMode={pickMode}
            onPickCoordinate={({ latitude: selectedLat, longitude: selectedLon }) => {
              setLatitude(selectedLat.toFixed(6));
              setLongitude(selectedLon.toFixed(6));
              setPickMode(false);
            }}
          />
        </div>
      </section>

      <section className="community-status-card">
        <h2>Check a report</h2>
        <form onSubmit={lookup} className="community-lookup">
          <input aria-label="Report ID" required value={lookupId} onChange={(event) => setLookupId(event.target.value)} placeholder="Paste your report ID" />
          <button className="community-submit" type="submit">Check status</button>
        </form>
        {lookupResult && <p role="status">Status: <b>{lookupResult.status}</b> · {lookupResult.district} · submitted {new Date(lookupResult.submitted_at).toLocaleString()}</p>}
      </section>

      <section className="community-review-card">
        <h2>Reviewer workspace</h2>
        <p>Reviewer actions are disabled unless the API server has a separately configured HILLCARE_REVIEWER_TOKEN. The token is not stored in the browser.</p>
        <div className="community-lookup">
          <input type="password" autoComplete="off" aria-label="Reviewer token" value={reviewerToken} onChange={(event) => setReviewerToken(event.target.value)} placeholder="Reviewer token" />
          <button type="button" className="community-submit" onClick={loadQueue} disabled={!reviewerToken}>Load review queue</button>
        </div>
        {reviewError && <p role="alert" className="community-error">{reviewError}</p>}
        {reviewQueue.map((report) => <article className="community-review-item" key={report.id}>
          <div><b>{report.subject}</b><span>{report.category} · {report.district} · {report.status}</span><span>{report.latitude}, {report.longitude}</span><p>{report.description}</p><small>Evidence: {report.evidence_source}{report.evidence_url ? ` · ${report.evidence_url}` : ''}</small></div>
          <label>Decision
            <select value={reviewStatus} onChange={(event) => setReviewStatus(event.target.value as CommunityStatus)}>
              {statuses.filter((status) => status !== 'pending').map((status) => <option key={status}>{status}</option>)}
            </select>
          </label>
          <label>Review note
            <input minLength={3} value={reviewNote} onChange={(event) => setReviewNote(event.target.value)} placeholder="Evidence checked and decision" />
          </label>
          <button type="button" className="community-submit" disabled={reviewNote.trim().length < 3} onClick={() => review(report)}>Save review</button>
        </article>)}
      </section>
    </main>
  );
};
