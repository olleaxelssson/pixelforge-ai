/**
 * Pure pixel-buffer operations for the editor. Buffers are RGBA
 * Uint8ClampedArray, row-major, length = width * height * 4.
 * All functions return new buffers (immutability enables snapshot undo/redo).
 */

export type RGBA = [number, number, number, number];

export function createBuffer(width: number, height: number): Uint8ClampedArray {
  return new Uint8ClampedArray(width * height * 4);
}

export function cloneBuffer(buffer: Uint8ClampedArray): Uint8ClampedArray {
  return new Uint8ClampedArray(buffer);
}

export function getPixel(
  buffer: Uint8ClampedArray,
  width: number,
  x: number,
  y: number,
): RGBA {
  const i = (y * width + x) * 4;
  return [buffer[i], buffer[i + 1], buffer[i + 2], buffer[i + 3]];
}

export function setPixel(
  buffer: Uint8ClampedArray,
  width: number,
  height: number,
  x: number,
  y: number,
  color: RGBA,
): void {
  if (x < 0 || y < 0 || x >= width || y >= height) return;
  const i = (y * width + x) * 4;
  buffer[i] = color[0];
  buffer[i + 1] = color[1];
  buffer[i + 2] = color[2];
  buffer[i + 3] = color[3];
}

export function drawLine(
  buffer: Uint8ClampedArray,
  width: number,
  height: number,
  x0: number,
  y0: number,
  x1: number,
  y1: number,
  color: RGBA,
): Uint8ClampedArray {
  const out = cloneBuffer(buffer);
  // Bresenham's line algorithm.
  let [cx, cy] = [x0, y0];
  const dx = Math.abs(x1 - x0);
  const dy = -Math.abs(y1 - y0);
  const sx = x0 < x1 ? 1 : -1;
  const sy = y0 < y1 ? 1 : -1;
  let err = dx + dy;
  for (;;) {
    setPixel(out, width, height, cx, cy, color);
    if (cx === x1 && cy === y1) break;
    const e2 = 2 * err;
    if (e2 >= dy) {
      err += dy;
      cx += sx;
    }
    if (e2 <= dx) {
      err += dx;
      cy += sy;
    }
  }
  return out;
}

export function drawRect(
  buffer: Uint8ClampedArray,
  width: number,
  height: number,
  x0: number,
  y0: number,
  x1: number,
  y1: number,
  color: RGBA,
  filled: boolean,
): Uint8ClampedArray {
  const out = cloneBuffer(buffer);
  const [minX, maxX] = [Math.min(x0, x1), Math.max(x0, x1)];
  const [minY, maxY] = [Math.min(y0, y1), Math.max(y0, y1)];
  for (let y = minY; y <= maxY; y++) {
    for (let x = minX; x <= maxX; x++) {
      const onEdge = x === minX || x === maxX || y === minY || y === maxY;
      if (filled || onEdge) setPixel(out, width, height, x, y, color);
    }
  }
  return out;
}

export function drawEllipse(
  buffer: Uint8ClampedArray,
  width: number,
  height: number,
  x0: number,
  y0: number,
  x1: number,
  y1: number,
  color: RGBA,
  filled: boolean,
): Uint8ClampedArray {
  const out = cloneBuffer(buffer);
  const cx = (x0 + x1) / 2;
  const cy = (y0 + y1) / 2;
  const rx = Math.max(Math.abs(x1 - x0) / 2, 0.5);
  const ry = Math.max(Math.abs(y1 - y0) / 2, 0.5);
  const [minX, maxX] = [Math.min(x0, x1), Math.max(x0, x1)];
  const [minY, maxY] = [Math.min(y0, y1), Math.max(y0, y1)];
  const inside = (x: number, y: number): boolean =>
    ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1;
  for (let y = minY; y <= maxY; y++) {
    for (let x = minX; x <= maxX; x++) {
      if (!inside(x, y)) continue;
      if (filled) {
        setPixel(out, width, height, x, y, color);
      } else {
        const onEdge =
          !inside(x - 1, y) || !inside(x + 1, y) || !inside(x, y - 1) || !inside(x, y + 1);
        if (onEdge) setPixel(out, width, height, x, y, color);
      }
    }
  }
  return out;
}

export function floodFill(
  buffer: Uint8ClampedArray,
  width: number,
  height: number,
  x: number,
  y: number,
  color: RGBA,
): Uint8ClampedArray {
  const out = cloneBuffer(buffer);
  if (x < 0 || y < 0 || x >= width || y >= height) return out;
  const target = getPixel(out, width, x, y);
  if (target.every((v, i) => v === color[i])) return out;
  const stack: Array<[number, number]> = [[x, y]];
  while (stack.length > 0) {
    const [px, py] = stack.pop() as [number, number];
    if (px < 0 || py < 0 || px >= width || py >= height) continue;
    const current = getPixel(out, width, px, py);
    if (!current.every((v, i) => v === target[i])) continue;
    setPixel(out, width, height, px, py, color);
    stack.push([px + 1, py], [px - 1, py], [px, py + 1], [px, py - 1]);
  }
  return out;
}

export function shiftBuffer(
  buffer: Uint8ClampedArray,
  width: number,
  height: number,
  dx: number,
  dy: number,
): Uint8ClampedArray {
  const out = createBuffer(width, height);
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const sx = x - dx;
      const sy = y - dy;
      if (sx < 0 || sy < 0 || sx >= width || sy >= height) continue;
      setPixel(out, width, height, x, y, getPixel(buffer, width, sx, sy));
    }
  }
  return out;
}

export function mergeLayers(
  layers: Uint8ClampedArray[],
  width: number,
  height: number,
): Uint8ClampedArray {
  const out = createBuffer(width, height);
  for (const layer of layers) {
    for (let i = 0; i < out.length; i += 4) {
      const alpha = layer[i + 3] / 255;
      if (alpha === 0) continue;
      const base = out[i + 3] / 255;
      const outAlpha = alpha + base * (1 - alpha);
      for (let c = 0; c < 3; c++) {
        out[i + c] =
          outAlpha === 0
            ? 0
            : (layer[i + c] * alpha + out[i + c] * base * (1 - alpha)) / outAlpha;
      }
      out[i + 3] = outAlpha * 255;
    }
  }
  return out;
}

export function hexToRgba(hex: string, alpha = 255): RGBA {
  const value = hex.replace("#", "");
  return [
    parseInt(value.slice(0, 2), 16),
    parseInt(value.slice(2, 4), 16),
    parseInt(value.slice(4, 6), 16),
    alpha,
  ];
}
