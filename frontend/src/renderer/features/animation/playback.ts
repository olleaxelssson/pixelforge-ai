/** Pure playback helpers for the animation timeline (M18). */

/** The next frame index during playback.
 *
 * Looping actions wrap to 0; non-looping actions clamp on the last frame (holds the final pose).
 */
export function nextFrame(index: number, count: number, loop: boolean): number {
  if (count <= 0) return 0;
  const next = index + 1;
  if (next < count) return next;
  return loop ? 0 : count - 1;
}

/** The previous frame index that an onion-skin ghost should show (null on the first frame). */
export function onionFrame(index: number, count: number, loop: boolean): number | null {
  if (index > 0) return index - 1;
  return loop && count > 1 ? count - 1 : null;
}
