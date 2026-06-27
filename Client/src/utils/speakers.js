const PALETTE = [
  "#2f5fff",
  "#c0392b",
  "#1a7431",
  "#9a6700",
  "#6f42c1",
  "#0e7490",
  "#be185d",
  "#4d5b00",
];

export function speakerColor(label) {
  if (!label) return "#5b6470";
  let hash = 0;
  for (let i = 0; i < label.length; i++) {
    hash = (hash * 31 + label.charCodeAt(i)) >>> 0;
  }
  return PALETTE[hash % PALETTE.length];
}

export function formatSpeakerLabel(label) {
  if (!label) return "Unknown speaker";
  const match = label.match(/(\d+)$/);
  if (match) {
    return `Speaker ${parseInt(match[1], 10) + 1}`;
  }
  return label;
}

export function speakerDisplayName(speakerOrLabel) {
  if (typeof speakerOrLabel === "string") {
    return formatSpeakerLabel(speakerOrLabel);
  }
  return speakerOrLabel?.display_name || formatSpeakerLabel(speakerOrLabel?.speaker_label);
}
