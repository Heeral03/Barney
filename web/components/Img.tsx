/* eslint-disable @next/next/no-img-element */
import type { ImgHTMLAttributes } from "react";

/** Product pictures come from many shops, so they are plain <img>: no allow-list of hosts to maintain. */
export function Img(props: ImgHTMLAttributes<HTMLImageElement>) {
  return <img referrerPolicy="no-referrer" loading="lazy" alt="" {...props} />;
}
