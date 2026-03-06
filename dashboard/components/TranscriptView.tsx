// dashboard/components/TranscriptView.tsx
'use client';
import { useEffect, useRef, useState } from 'react';

export interface Segment {
  meeting_id?: string;
  speaker: string;
  text: string;
  timestamp: string;
}

interface Props {
  meetingId: string;
  initialSegments: Segment[];
  isLive: boolean;
}

export function TranscriptView({ meetingId, initialSegments, isLive }: Props) {
  const [segments, setSegments] = useState<Segment[]>(initialSegments);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isLive) return;
    const wsUrl = process.env.NEXT_PUBLIC_BOT_WS_URL ?? 'ws://localhost:8765';
    const ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
      const segment: Segment = JSON.parse(event.data);
      if (!segment.meeting_id || segment.meeting_id === meetingId) {
        setSegments((prev) => [...prev, segment]);
      }
    };

    ws.onerror = () => console.warn('WS connection error');

    return () => ws.close();
  }, [meetingId, isLive]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [segments]);

  if (segments.length === 0 && !isLive) {
    return <p className="text-gray-400 text-sm p-4">No transcript available.</p>;
  }

  return (
    <div className="space-y-3 max-h-[600px] overflow-y-auto p-4">
      {segments.map((seg, i) => (
        <div key={i} className="flex gap-3">
          <span className="text-xs text-gray-400 w-16 shrink-0 pt-0.5 font-mono">
            {seg.timestamp}
          </span>
          <div>
            <span className="font-semibold text-sm text-gray-800">{seg.speaker}: </span>
            <span className="text-sm text-gray-700">{seg.text}</span>
          </div>
        </div>
      ))}
      {isLive && (
        <div className="flex items-center gap-2 text-green-600 text-xs pt-2">
          <span className="inline-block w-2 h-2 rounded-full bg-green-500 animate-pulse" />
          Live transcription active
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  );
}
