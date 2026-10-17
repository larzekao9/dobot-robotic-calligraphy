import type { Layout } from "../api/types";

export const DEFAULT_LAYOUT: Layout = {
  paper: "A4",
  width_mm: null,
  height_mm: null,
  landscape: false,
  margin_mm: 15,
  char_size_mm: 40,
  spacing_mm: 8,
  orientation: "horizontal",
  dip_every_chars: 2,
  auto_fit: true,
};
