import { headers } from "next/headers";
import { SiteNav } from "./site-nav";

export async function SiteNavServer() {
  const headersList = await headers();
  const pathname = headersList.get("x-current-path") || "/";

  return <SiteNav pathname={pathname} />;
}
