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

const importInput = z.object({
  source: z.string().min(1).max(1024),
  concept_type: z.string().min(1).max(256),
  id_column: z
    .string()
    .max(256)
    .optional()
    .transform((value) => value || undefined),
  // Astro decodes HTML checkboxes to booleans for form actions; keep the
  // literal HTML value accepted too so the boundary is explicit and bounded.
  overwrite: z
    .union([z.boolean(), z.literal("on")])
    .optional()
    .transform((value) => value === true || value === "on"),
  on_conflict: z.enum(["skip", "verify-identical"]).default("skip"),
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

  importPreview: defineAction({
    accept: "form",
    input: importInput,
    handler: async (input) => {
      try {
        return {
          input,
          mutation: await okf.importPreview(input),
        };
      } catch (error) {
        actionFailure(error);
      }
    },
  }),

  importCommit: defineAction({
    accept: "form",
    input: importInput,
    handler: async (input) => {
      try {
        return {
          input,
          mutation: await okf.importWrite(input),
        };
      } catch (error) {
        actionFailure(error);
      }
    },
  }),
};
