import { ActionError, defineAction } from "astro:actions";
import { z } from "astro:schema";

import { okf } from "../lib/server/okf";

const editInput = z.object({
  concept_id: z.string().min(1),
  body: z.string().max(4 * 1024 * 1024),
  expected_source_digest: z.string().regex(/^sha256:[0-9a-f]{64}$/u),
});

const applyPreviewInput = z.object({
  sql: z.string().min(1).max(256 * 1024),
});

const applyCommitInput = applyPreviewInput.extend({
  // The parser owns the token format and semantics. Astronauta only transports
  // an opaque, bounded value from the reviewed preview back to the commit.
  preview_token: z.string().min(1).max(4096),
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
    input: applyPreviewInput,
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

  applyCommit: defineAction({
    accept: "form",
    input: applyCommitInput,
    handler: async (input) => {
      try {
        return {
          input,
          mutation: await okf.applyWrite(input.sql, input.preview_token),
        };
      } catch (error) {
        actionFailure(error);
      }
    },
  }),
};
