import { useState } from "react";

export default function FrameGrid({ frames, label }) {
  const [modal, setModal] = useState(null); // { src, index }
  const isShoplifting = label === "Shoplifting";

  return (
    <div>
      <h3 className="text-white font-bold text-sm uppercase tracking-widest mb-3">
        📷 Sampled Frames (YOLO-cropped, 16 frames)
      </h3>

      <div className="grid grid-cols-4 gap-2">
        {frames.map((f) => (
          <div
            key={f.frame_index}
            onClick={() =>
              setModal({
                src: `data:image/jpeg;base64,${f.image_b64}`,
                index: f.frame_index,
              })
            }
            className={`relative rounded-lg overflow-hidden cursor-zoom-in border transition hover:scale-105 hover:z-10 ${
              isShoplifting
                ? "border-shoplifting/40 hover:border-shoplifting"
                : "border-normal/40 hover:border-normal"
            }`}
          >
            <img
              src={`data:image/jpeg;base64,${f.image_b64}`}
              alt={`Frame ${f.frame_index}`}
              className="w-full aspect-square object-cover"
              loading="lazy"
            />
            <div className="absolute bottom-0 left-0 right-0 bg-black/60 text-center text-xs py-0.5 text-muted">
              F{f.frame_index}
            </div>
          </div>
        ))}
      </div>

      {/* Fullscreen modal */}
      {modal && (
        <div
          className="fixed inset-0 z-50 bg-black/90 flex items-center justify-center p-4"
          onClick={() => setModal(null)}
        >
          <div
            className="relative max-w-2xl w-full"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              onClick={() => setModal(null)}
              className="absolute -top-8 right-0 text-white text-sm hover:text-accent transition"
            >
              ✕ Close
            </button>
            <img
              src={modal.src}
              alt={`Frame ${modal.index} fullscreen`}
              className="w-full rounded-xl border border-border"
            />
            <p className="text-center text-muted text-sm mt-2">
              Frame {modal.index} / 16
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
