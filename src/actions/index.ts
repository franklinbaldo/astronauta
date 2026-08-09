import { ActionError, defineAction } from "astro:actions";
import { z } from "astro:schema";

import { okf } from "../lib/server/okf";

const editInput = z.object({
  concept_id: z.string().min(1),
  body: z.string().max(4 * 1024 * 1024),
  expected_source_digest: z.string().regex(/^sha256:[0-9a-f]{64}$/u),
});

const applyInput = z.object({
  sql: z.string().min(1).max(256 * 1024),
});

function actionFailure(error: unknown): never {
  const message = error instanceof Error ? error.message : String(error);
  throw new ActionError({ code: "BAD_REQUEST", message });
}

export const server = {
  editPreview: defineAction({
    accept: "form",
    input: editInput,
    handler: async (input) => {
      try {
        return {
          input,
          mutation: await okf.editPreview(input),
        };
      } catch (error) {
        actionFailure(error);
      }
    },
  }),

  editCommit: defineAction({
    accept: "form",
    input: editInput,
    handler: async (input) => {
      try {
        return {
          input,
          mutation: await okf.editWrite(input),
        };
      } catch (error) {
        actionFailure(error);
      }
    },
  }),

  applyPreview: defineAction({
    accept: "form",
    input: applyInput,
    handler: async (input) => {
      try {
        return {
          input,
          mutation: await okf.applyPreview(input.sql),
        };
      } catch (error) {
        actionFailure(error);
      }
    },
  }),
};
