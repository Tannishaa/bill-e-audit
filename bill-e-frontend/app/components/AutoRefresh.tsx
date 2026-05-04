'use client'

import { useEffect, useTransition } from 'react';
import { useRouter } from 'next/navigation';

export default function AutoRefresh({ interval = 3000 }: { interval?: number }) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    const timer = setInterval(() => {
      // Only trigger a new refresh if we aren't already waiting for one to finish
      if (!isPending) {
        startTransition(() => {
          router.refresh();
        });
      }
    }, interval);

    return () => clearInterval(timer);
  }, [router, interval, isPending]); // Added isPending to dependency array

  return null; 
}