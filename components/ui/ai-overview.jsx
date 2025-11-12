import PropTypes from "prop-types";

/**
 * AIOverviewCard
 * Props:
 *   - text: string (the AI overview content to display)
 * Usage:
 *   <AIOverviewCard text="This analysis demonstrates..." />
 */
export default function AIOverviewCard({ text }) {
  return (
    <div
      className="relative overflow-hidden rounded-xl border border-slate-200/50 bg-gradient-to-br from-white via-slate-50 to-blue-50/60 shadow-lg transition-shadow hover:shadow-xl"
      style={{
        minHeight: 140,
        maxWidth: 700,
        margin: "auto",
      }}
    >
      <div className="px-6 py-6 md:px-8 md:py-8">
        <div className="flex items-center gap-3 mb-3">
          <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-cyan-500/80 via-cyan-400/80 to-blue-500/80 shadow text-white text-xl font-bold select-none">
            <svg
              width="22"
              height="22"
              fill="none"
              viewBox="0 0 24 24"
              className="inline-block"
            >
              <path
                d="M12 2c-5.52 0-10 4.48-10 10s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 17.93c-3.95.49-7.44-2.79-7.93-6.72A8.013 8.013 0 0 1 4 12c0-4.42 3.58-8 8-8 .34 0 .67.02 1 .07v15.86zm6.9-2.54A7.995 7.995 0 0 1 12 20c-1.23 0-2.4-.28-3.47-.79l11.37-11.37c.51 1.07.79 2.24.79 3.47 0 2.13-.83 4.07-2.19 5.58z"
                fill="currentColor"
                opacity=".2"
              />
              <path
                d="M17.9606 8.35104C18.1941 8.58462 18.1941 8.96538 17.9606 9.19896L9.19897 17.9606C8.96538 18.1941 8.58463 18.1941 8.35104 17.9606C8.11745 17.727 8.11745 17.3463 8.35104 17.1127L17.1127 8.35104C17.3463 8.11746 17.727 8.11746 17.9606 8.35104Z"
                fill="currentColor"
              />
            </svg>
          </span>
          <span className="text-base font-semibold text-slate-800 tracking-tight">
            AI Overview
          </span>
        </div>
        <div className="text-slate-700 text-[1.08rem] leading-relaxed whitespace-pre-line">
          {text}
        </div>
      </div>
      <div
        className="pointer-events-none absolute inset-0 rounded-xl"
        aria-hidden="true"
        style={{
          background:
            "radial-gradient(ellipse at top right, #bae6fd88 10%, transparent 70%)",
          zIndex: 0,
        }}
      ></div>
    </div>
  );
}

AIOverviewCard.propTypes = {
  text: PropTypes.string.isRequired,
};
