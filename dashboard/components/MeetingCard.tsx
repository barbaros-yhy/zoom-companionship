// dashboard/components/MeetingCard.tsx
import Link from 'next/link';

interface Meeting {
  id: string;
  title: string;
  date: string;
  status: 'ongoing' | 'completed';
  participants: string;
}

export function MeetingCard({ meeting }: { meeting: Meeting }) {
  const participants = (() => {
    try { return JSON.parse(meeting.participants) as string[]; } catch { return []; }
  })();

  return (
    <Link href={`/meetings/${meeting.id}`}>
      <div className="border rounded-lg p-4 hover:bg-gray-50 cursor-pointer transition-colors">
        <div className="flex justify-between items-start">
          <h3 className="font-medium text-gray-900">{meeting.title}</h3>
          <span className={`text-xs px-2 py-1 rounded-full font-medium ${
            meeting.status === 'ongoing'
              ? 'bg-green-100 text-green-700'
              : 'bg-gray-100 text-gray-600'
          }`}>
            {meeting.status === 'ongoing' ? '● Live' : 'Completed'}
          </span>
        </div>
        <p className="text-sm text-gray-500 mt-1">
          {new Date(meeting.date).toLocaleString()}
        </p>
        {participants.length > 0 && (
          <p className="text-xs text-gray-400 mt-1">{participants.join(', ')}</p>
        )}
      </div>
    </Link>
  );
}
