import createClient from "openapi-fetch";
import type { paths } from "./schema";

export type { paths, components } from "./schema";

/** Web/native fetch transport. Mini-programs will supply a platform adapter. */
export function createFactoryFlowClient(baseUrl = "", transport: typeof fetch = fetch) {
  return createClient<paths>({ baseUrl, fetch: transport });
}
