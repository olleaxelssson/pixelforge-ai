import { api } from "../../api/client";
import type { Job } from "../../api/types";
import { useEditorStore } from "../../state/editorStore";
import { useGenerationStore } from "../../state/generationStore";
import { TilePreview } from "./TilePreview";

function openInEditor(filename: string, width: number, height: number) {
  const image = new Image();
  image.crossOrigin = "anonymous";
  image.onload = () => {
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext("2d");
    if (!context) return;
    context.drawImage(image, 0, 0);
    const data = context.getImageData(0, 0, width, height).data;
    useEditorStore.getState().loadImageData(data, width, height);
  };
  image.src = api.imageUrl(filename);
}

function JobCard({ job }: { job: Job }) {
  const cancel = useGenerationStore((state) => state.cancel);
  const active = job.status === "queued" || job.status === "running";
  return (
    <div className="job-card">
      <div className="job-header">
        <span className={`job-status ${job.status}`}>{job.status}</span>
        <span>{job.request.prompt}</span>
        {active && (
          <>
            <div className="progress-bar">
              <div style={{ width: `${job.progress.percent}%` }} />
            </div>
            <span>{job.progress.stage}</span>
            <button className="small-button" onClick={() => void cancel(job.id)}>
              Cancel
            </button>
          </>
        )}
      </div>
      {job.error && <div className="error-text">{job.error}</div>}
      {job.result && (
        <div className="result-images">
          {job.result.images.map((image) => (
            <div key={image.filename} className="result-item">
              <img
                className="result-image"
                src={api.imageUrl(image.filename)}
                title={`seed ${image.seed} — click to edit`}
                onClick={() => openInEditor(image.filename, image.width, image.height)}
              />
              {job.request.tileable && <TilePreview filename={image.filename} />}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function ResultsPanel() {
  const jobs = useGenerationStore((state) => state.jobs);
  const jobOrder = useGenerationStore((state) => state.jobOrder);
  return (
    <section className="results">
      {jobOrder.length === 0 && (
        <p style={{ color: "var(--text-dim)" }}>
          Generated sprites appear here. Click a result to open it in the editor.
        </p>
      )}
      {jobOrder.map((id) => (
        <JobCard key={id} job={jobs[id]} />
      ))}
    </section>
  );
}
