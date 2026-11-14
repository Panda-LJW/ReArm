// 标签单独占上下两条带，图形只在中间绘制。实际文字高度参与排版。
export function observationLayout(width, height, sizes, gap = 4) {
  const inset = 24; // 留出 8px 外距和 14px 取景角标；标签间距仍由 gap 控制。
  const columns = 2, split = Math.ceil(sizes.length / columns / 2) * columns;
  const groups = [sizes.slice(0, split), sizes.slice(split)];
  const rowHeights = groups.map(group => Array.from({ length: Math.ceil(group.length / columns) }, (_, row) =>
    Math.max(...group.slice(row * columns, (row + 1) * columns).map(size => size.height))));
  const bands = rowHeights.map(rows => rows.reduce((sum, value) => sum + value + gap, 0));
  const plot = { left: inset, top: inset + bands[0], width: width - 2 * inset,
    height: Math.max(1, height - 2 * inset - bands[0] - bands[1]) };
  const labels = [];
  groups.forEach((group, side) => {
    let top = side === 0 ? inset : height - inset - bands[1];
    group.forEach((size, i) => {
      if (i && i % columns === 0) top += rowHeights[side][i / columns - 1] + gap;
      labels.push({ left: i % columns ? width - inset - size.width : inset, top, ...size });
    });
  });
  return { plot, labels };
}

export function imageTransform(plot, image) {
  const scale = Math.min(plot.width / image.width, plot.height / image.height);
  return { scale, x: plot.left + (plot.width - image.width * scale) / 2,
    y: plot.top + (plot.height - image.height * scale) / 2 };
}
