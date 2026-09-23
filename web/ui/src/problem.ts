import { ApiError } from "./api";

export interface Problem {
  message: string;
  detail: string;
}

// The summary is what the operator can act on; the status and whatever the
// panel actually answered stay behind the detail toggle.
export function describe(error: unknown, message?: string): Problem {
  if (error instanceof ApiError) {
    return {
      message: message ?? error.message,
      detail: `${error.status} - ${error.message}`,
    };
  }
  return {
    message: message ?? "Could not reach the panel",
    detail: error instanceof Error ? error.message : String(error),
  };
}
