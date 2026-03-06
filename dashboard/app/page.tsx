// dashboard/app/page.tsx
import { MeetingCard } from '@/components/MeetingCard';
import Link from 'next/link';

async function getMeetings() {
  const apiUrl = process.env.API_URL ?? 'http://localhost:3001';
  try {
    const res = await fetch(`${apiUrl}/meetings`, {
      cache: 'no-store',
      next: { revalidate: 0 },
    });
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

export default async function Home() {
  const meetings = await getMeetings();

  return (
    <main className="max-w-2xl mx-auto p-6">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Zoom Companion</h1>
          <p className="text-sm text-gray-500">Meeting transcription & summaries</p>
        </div>
        <Link
          href="/meetings/new"
          className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
        >
          + New Meeting
        </Link>
      </div>

      <div className="space-y-3">
        {meetings.length === 0 ? (
          <div className="text-center py-16 text-gray-400">
            <p className="text-lg">No meetings yet</p>
            <p className="text-sm mt-1">Start by adding a Zoom meeting URL</p>
          </div>
        ) : (
          meetings.map((m: Parameters<typeof MeetingCard>[0]['meeting']) => (
            <MeetingCard key={m.id} meeting={m} />
          ))
        )}
      </div>
    </main>
  );
}
