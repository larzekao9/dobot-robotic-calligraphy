import { describe, expect, it } from "vitest";
import { validateName } from "./validateName";

describe("validateName", () => {
  it.each(["Ana", "José Luis", "Ana-María", "O'Higgins", "Núñez Peña", "Müller", "a"])(
    "acepta %s",
    (name) => expect(validateName(name)).toBeNull(),
  );

  it.each([
    ["", "Escribe"],
    ["   ", "Escribe"],
    ["Ana123", "Solo se permiten"],
    ["<script>", "Solo se permiten"],
    ["李明", "Solo se permiten"],
    ["x".repeat(61), "60 caracteres"],
    ["a b c d e", "4 palabras"],
    ["a-b-c-d-e", "4 palabras"],
  ])("rechaza %j", (name, fragment) => {
    expect(validateName(name)).toContain(fragment);
  });

  it("acepta exactamente 60 caracteres y 4 palabras", () => {
    expect(validateName("x".repeat(60))).toBeNull();
    expect(validateName("a b c d")).toBeNull();
  });
});
