"use client";

import { Suspense, useEffect, useRef } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ConciergeChat } from "@/components/chat/ConciergeChat";
import { useConciergeChat } from "@/lib/chat";

function HomeContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { send } = useConciergeChat();
  const autoSentRef = useRef(false);

  // A UI-action-generated prompt (e.g. "Create as new Party record" on a
  // no-results Search) — one click sends a predefined prompt straight into
  // the same Concierge path a typed message would take, per the pivot
  // addendum's trigger types. Strip it from the URL right away so
  // reloading/back doesn't resend it. autoSentRef guards against React
  // Strict Mode's dev-only double-invoke of effects on mount — without it
  // this fired the prompt twice, submitting two separate requests.
  useEffect(() => {
    const prefilled = searchParams.get("prompt");
    if (prefilled && !autoSentRef.current) {
      autoSentRef.current = true;
      router.replace("/", { scroll: false });
      send(prefilled);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return <ConciergeChat variant="inline" />;
}

export default function Home() {
  return (
    <Suspense fallback={<div className="h-full bg-white dark:bg-zinc-950" />}>
      <HomeContent />
    </Suspense>
  );
}
