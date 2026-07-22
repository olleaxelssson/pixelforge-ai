import { useEffect, useState } from "react";

import { api } from "../../api/client";
import { decodeImage } from "../../api/image";
import { seamBadge, seamScore, type SeamScore } from "./tileView";

const REPEAT = 3; // NxN tiling preview
const CELL = 48; // displayed px per tile

/** A live NxN tiling preview + seamlessness readout for one generated sprite (M22). */
export function TilePreview({ filename }: { filename: string }) {
  const [open, setOpen] = useState(false);
  const [score, setScore] = useState<SeamScore | null>(null);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    decodeImage(api.imageUrl(filename))
      .then(({ data, width, height }) => {
        if (!cancelled) setScore(seamScore(data, width, height));
      })
      .catch(() => setScore(null));
    return () => {
      cancelled = true;
    };
  }, [open, filename]);

  const badge = score ? seamBadge(score) : null;

  return (
    <div className="tile-preview">
      <button className="small-button" onClick={() => setOpen((o) => !o)}>
        {open ? "Hide tiling" : "Preview tiling"}
      </button>
      {open && (
        <div className="tile-preview-body">
          <div
            className="tile-grid"
            style={{
              width: REPEAT * CELL,
              height: REPEAT * CELL,
              backgroundImage: `url(${api.imageUrl(filename)})`,
              backgroundSize: `${CELL}px ${CELL}px`,
            }}
            title={`${REPEAT}×${REPEAT} tiling`}
          />
          {badge && (
            <span className={`tile-badge ${badge.ok ? "ok" : "warn"}`}>
              {badge.percent}% · {badge.label}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
