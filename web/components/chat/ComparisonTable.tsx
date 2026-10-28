import { compact } from "@/lib/format";
import type { CompareTable } from "@/lib/types";
import { CheckIcon, StarIcon } from "../icons";
import { Img } from "../Img";

const Cell = ({ best, children, head }: { best?: boolean; children: React.ReactNode; head?: boolean }) => {
  const Tag = head ? "th" : "td";
  return <Tag className={`min-w-[170px] px-4 py-3 text-left align-top ${best ? "bg-[#faf8f5]" : ""}`}>{children}</Tag>;
};

const Label = ({ children }: { children: React.ReactNode }) => (
  <th scope="row" className="sticky left-0 z-10 w-[120px] min-w-[120px] bg-card px-4 py-3 text-left align-top text-[12.5px] font-normal text-muted">{children}</th>
);

const Section = ({ children, span }: { children: React.ReactNode; span: number }) => (
  <tr><th colSpan={span} className="bg-sidebar px-4 py-2 text-left text-[11px] font-medium uppercase tracking-[0.12em] text-faint">{children}</th></tr>
);

/** Side by side: options as columns. Price, seller and rating first, then specs, then how each option meets your needs. */
export function ComparisonTable({ table }: { table: CompareTable }) {
  const span = table.rows.length + 1;
  return (
    <div className="rise overflow-x-auto rounded-2xl border border-line bg-card">
      <table className="w-full border-collapse text-[13.5px]">
        <thead>
          <tr>
            <th className="w-[120px] min-w-[120px]" />
            {table.rows.map((r) => (
              <Cell key={r.number} head best={r.best}>
                <div className="grid h-16 w-16 place-items-center rounded-lg bg-[#f7f5f1]">{r.image_url ? <Img src={r.image_url} className="h-full w-full object-contain p-1 mix-blend-multiply" /> : null}</div>
                <p className="mt-2 line-clamp-3 font-medium leading-5">{r.title}</p>
                {r.best && <span className="mt-2 inline-block rounded-full bg-sage-bg px-2.5 py-0.5 text-[11px] text-sage-ink">Barney’s pick</span>}
              </Cell>
            ))}
          </tr>
        </thead>
        <tbody className="[&_tr:not(:first-child)]:border-t [&_tr]:border-line">
          <tr>
            <Label>Price</Label>
            {table.rows.map((r) => (
              <Cell key={r.number} best={r.best}>
                <span className="text-[16px] font-medium">{r.price_display}</span>
                {r.price_verified && <span className="ml-1.5 inline-flex items-center text-[12px] text-sage-ink"><CheckIcon /></span>}
              </Cell>
            ))}
          </tr>
          <tr>
            <Label>Sold by</Label>
            {table.rows.map((r) => (
              <Cell key={r.number} best={r.best}>
                <p>{r.seller}{r.seller_trusted === false ? " ⚠" : ""}</p>
                {r.link ? (
                  <a href={r.link} target="_blank" rel="noopener noreferrer" className="mt-2 inline-block rounded-lg bg-ink px-3.5 py-1.5 text-[12.5px] text-white transition hover:bg-ink/85">Buy</a>
                ) : (
                  <p className="mt-1 text-[12px] text-faint">no seller link yet</p>
                )}
              </Cell>
            ))}
          </tr>
          <tr>
            <Label>Rating</Label>
            {table.rows.map((r) => (
              <Cell key={r.number} best={r.best}>
                {r.rating ? <span className="inline-flex items-center gap-1.5"><StarIcon className="text-amber" />{r.rating}{r.rating_count ? <span className="text-faint">({compact(r.rating_count)})</span> : null}</span> : <span className="text-faint">no ratings</span>}
              </Cell>
            ))}
          </tr>

          {table.specs.length > 0 && <Section span={span}>Specifications</Section>}
          {table.specs.map((spec) => (
            <tr key={spec}>
              <Label>{spec}</Label>
              {table.rows.map((r) => (
                <Cell key={r.number} best={r.best}>{r.values[spec] || <span className="text-faint">not stated</span>}</Cell>
              ))}
            </tr>
          ))}

          {table.requirements.length > 0 && <Section span={span}>Your needs</Section>}
          {table.requirements.map((need) => (
            <tr key={need}>
              <Label>{need}</Label>
              {table.rows.map((r) => {
                const m = r.matches[need] ?? "unknown";
                return (
                  <Cell key={r.number} best={r.best}>
                    {m === "yes" ? <span className="font-medium text-sage-ink">✓ Yes</span> : m === "no" ? <span className="font-medium text-danger">✗ No</span> : <span className="text-faint">? Not stated</span>}
                  </Cell>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
