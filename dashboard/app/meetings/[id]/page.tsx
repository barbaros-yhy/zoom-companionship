// dashboard/app/meetings/[id]/page.tsx
import { TranscriptView, Segment } from '@/components/TranscriptView';
import { SummaryView } from '@/components/SummaryView';
import Link from 'next/link';

interface Meeting {
  id: string;
  title: string;
  date: string;
  status: 'ongoing' | 'completed';
  summary?: string;
  action_items?: string;
}

async function getMeeting(id: string): Promise<Meeting | null> {
  const apiUrl = process.env.API_URL ?? 'http://localhost:3001';
  try {
    const res = await fetch(`${apiUrl}/meetings/${id}`, { cache: 'no-store' });
    if (!res.ok) return null;
    return res.json();
  } catch { return null; }
}

async function getSegments(id: string): Promise<Segment[]> {
  const apiUrl = process.env.API_URL ?? 'http://localhost:3001';
  try {
    const res = await fetch(`${apiUrl}/meetings/${id}/segments`, { cache: 'no-store' });
    if (!res.ok) return [];
    return res.json();
  } catch { return []; }
}

export default async function MeetingPage({ params }: { params: { id: string } }) {
  const meeting = await getMeeting(params.id);

  if (!meeting) {
    return (
      <main className="max-w-3xl mx-auto p-6">
        <p className="text-gray-500">Meeting not found.</p>
        <Link href="/" className="text-blue-600 text-sm">← Back to meetings</Link>
      </main>
    );
  }

  const isLive = meeting.status === 'ongoing';
  const initialSegments = isLive ? [] : await getSegments(meeting.id);
  const actionItems: string[] = (() => {
    try { return JSON.parse(meeting.action_items ?? '[]'); } catch { return []; }
  })();

  return (
    <main className="max-w-3xl mx-auto p-6">
      <div className="mb-4">
        <Link href="/" className="text-sm text-gray-500 hover:text-gray-700">← All meetings</Link>
      </div>

      <div className="flex justify-between items-start mb-4">
        <div>
          <h1 className="text-xl font-bold text-gray-900">{meeting.title}</h1>
          <p className="text-sm text-gray-500">{new Date(meeting.date).toLocaleString()}</p>
        </div>
        <span className={`text-sm px-3 py-1 rounded-full font-medium ${
          isLive ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'
        }`}>
          {isLive ? '● Live' : 'Completed'}
        </span>
      </div>

      <div className="border rounded-lg mb-6">
        <div className="border-b px-4 py-2">
          <h2 className="text-sm font-medium text-gray-600">Transcript</h2>
        </div>
        <TranscriptView
          meetingId={meeting.id}
          initialSegments={initialSegments}
          isLive={isLive}
        />
      </div>

      {!isLive && meeting.summary && (
        <div className="border rounded-lg p-4">
          <SummaryView summary={meeting.summary} actionItems={actionItems} />
        </div>
      )}
    </main>
  );
}
