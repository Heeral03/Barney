"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useBarney } from "@/lib/barney";
import type { Form } from "@/lib/types";

const SKIP = "Just show me options"; // same words the back end reads as "stop asking"

/** Every question at once. Tap as many answers as fit in each, or write your own; one button sends them all. */
const label = (t: string) => { const s = t.replace(/_/g, " "); return s.charAt(0).toUpperCase() + s.slice(1); };

export function Questionnaire({ form }: { form: Form }) {
  const { send } = useBarney();
  const [picked, setPicked] = useState<Record<string, string[]>>({});
  const [own, setOwn] = useState<Record<string, string>>({});

  const toggle = (topic: string, option: string) =>
    setPicked((p) => {
      const now = p[topic] ?? [];
      return { ...p, [topic]: now.includes(option) ? now.filter((o) => o !== option) : [...now, option] };
    });

  // What the shopper chose per question, with their own words added to the buttons they tapped.
  const answers: Record<string, string[]> = {};
  for (const q of form.questions) {
    const values = [...(picked[q.topic] ?? []), ...(own[q.topic]?.trim() ? [own[q.topic].trim()] : [])];
    if (values.length) answers[q.topic] = values;
  }
  const answered = Object.keys(answers).length;

  function submit() {
    const summary = form.questions
      .filter((q) => answers[q.topic])
      .map((q) => `${label(q.topic)}: ${answers[q.topic].join(", ")}`)
      .join(" · ");
    api.track("form_submitted");
    send(summary, answers);
  }

  return (
    <div className="max-w-[760px] space-y-7 rounded-2xl border border-line bg-card p-6">
      {form.questions.map((q) => (
        <fieldset key={q.topic}>
          <legend className="text-[15px] font-medium">{q.question}</legend>
          <div className="mt-3 flex flex-wrap gap-2.5">
            {q.options.map((o) => {
              const on = (picked[q.topic] ?? []).includes(o);
              return (
                <button
                  key={o}
                  type="button"
                  aria-pressed={on}
                  onClick={() => toggle(q.topic, o)}
                  className={`rounded-full border px-4 py-2 text-[13.5px] transition ${on ? "border-ink bg-ink text-white" : "border-line-strong bg-paper text-ink/85 hover:border-ink/40 hover:bg-tint/60"}`}
                >
                  {o}
                </button>
              );
            })}
          </div>
          <input
            value={own[q.topic] ?? ""}
            onChange={(e) => setOwn((s) => ({ ...s, [q.topic]: e.target.value }))}
            placeholder="Something else? Write it here"
            aria-label={`${q.question} Your own answer`}
            className="mt-3 h-10 w-full max-w-sm rounded-lg border border-line-strong bg-paper px-3 text-[13.5px] text-ink outline-none placeholder:text-faint focus:border-ink/50"
          />
        </fieldset>
      ))}

      <div className="flex flex-wrap items-center gap-3 border-t border-line pt-5">
        <button
          type="button"
          onClick={submit}
          disabled={answered === 0}
          className="rounded-full bg-ink px-6 py-2.5 text-[14px] text-white transition hover:bg-ink/85 disabled:opacity-40"
        >
          {answered === 0 ? "Pick at least one" : `Find my options (${answered} of ${form.questions.length} answered)`}
        </button>
        <button type="button" onClick={() => { api.track("form_skipped"); send(SKIP); }} className="rounded-full px-4 py-2.5 text-[14px] text-muted underline-offset-4 transition hover:text-ink hover:underline">
          {SKIP}
        </button>
      </div>
    </div>
  );
}
