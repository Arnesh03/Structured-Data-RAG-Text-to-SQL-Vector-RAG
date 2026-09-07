import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /*
    A static export. Every component here is client-side and fetches from the
    API at runtime, so there is no server rendering to give up - and the output
    is a folder of files FastAPI can serve directly, which is what lets the
    whole project deploy as one container behind one URL.
  */
  output: "export",
  images: { unoptimized: true },
  trailingSlash: true,
};

export default nextConfig;
