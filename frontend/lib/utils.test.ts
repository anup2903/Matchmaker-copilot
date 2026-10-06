import { describe, expect, it } from "vitest";
import { extractErrorMessage } from "./api";
import { STATUS_STYLE, categoryLabel, isStatedViolation, yesNoUnknown } from "./utils";

describe("status presentation", () => {
  it("labels match the product copy", () => {
    expect(STATUS_STYLE.RED.label).toBe("RED — BLOCKED");
    expect(STATUS_STYLE.AMBER.label).toBe("AMBER — REVIEW");
    expect(STATUS_STYLE.GREEN.label).toBe("GREEN — GOOD TO SHARE");
  });
});

describe("formatting", () => {
  it("never guesses missing attributes", () => {
    expect(yesNoUnknown(null)).toBe("Unknown");
    expect(yesNoUnknown(undefined)).toBe("Unknown");
    expect(yesNoUnknown(true)).toBe("Yes");
    expect(yesNoUnknown(false)).toBe("No");
  });

  it("maps category keys to readable labels", () => {
    expect(categoryLabel("location_distance")).toBe("Location / distance");
    expect(categoryLabel("something_new")).toBe("something new");
  });
});

describe("violation types", () => {
  it("only stated / dealbreaker / soft count as violating a stated preference", () => {
    expect(isStatedViolation("dealbreaker")).toBe(true);
    expect(isStatedViolation("stated_preference")).toBe(true);
    expect(isStatedViolation("soft_preference")).toBe(true);
    expect(isStatedViolation("new_signal")).toBe(false);
    expect(isStatedViolation("unclear")).toBe(false);
  });
});

describe("error extraction", () => {
  it("reads structured API errors", () => {
    const e = extractErrorMessage(
      { detail: { code: "llm_unavailable", message: "The language model timed out.", fallback_available: true } },
      "x",
    );
    expect(e).toEqual({ message: "The language model timed out.", code: "llm_unavailable", fallbackAvailable: true });
  });

  it("reads FastAPI validation errors and falls back otherwise", () => {
    expect(extractErrorMessage({ detail: [{ msg: "String should have at least 1 character", loc: ["body", "rejection_note"] }] }, "x").message).toContain(
      "rejection_note",
    );
    expect(extractErrorMessage(null, "fallback").message).toBe("fallback");
  });
});
