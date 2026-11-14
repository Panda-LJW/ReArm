export function element(doc, tag, className = "", text = "") {
  const el = doc.createElement(tag);
  if (className) el.className = className;
  if (text) el.textContent = text;
  return el;
}

export function svgElement(doc, tag, attrs = {}) {
  const el = doc.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [key, value] of Object.entries(attrs)) el.setAttribute(key, String(value));
  return el;
}
