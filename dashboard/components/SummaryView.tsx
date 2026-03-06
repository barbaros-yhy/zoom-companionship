// dashboard/components/SummaryView.tsx
interface Props {
  summary: string;
  actionItems: string[];
}

export function SummaryView({ summary, actionItems }: Props) {
  const points = summary.split('\n').filter(Boolean);

  return (
    <div className="space-y-4">
      <div>
        <h2 className="font-semibold text-gray-800 mb-2">Summary</h2>
        <ul className="space-y-1">
          {points.map((point, i) => (
            <li key={i} className="text-sm text-gray-700 flex gap-2">
              <span className="text-gray-400 shrink-0">•</span>
              <span>{point}</span>
            </li>
          ))}
        </ul>
      </div>

      {actionItems.length > 0 && (
        <div>
          <h2 className="font-semibold text-gray-800 mb-2">Action Items</h2>
          <ul className="space-y-1">
            {actionItems.map((item, i) => (
              <li key={i} className="text-sm text-gray-700 flex gap-2">
                <span className="text-gray-400 shrink-0">☐</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
