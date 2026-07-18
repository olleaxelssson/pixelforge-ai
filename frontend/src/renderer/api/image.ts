/** Image <-> base64 helpers shared by the QA, character, and palette panels.
 *
 * The backend's QA/character/extract endpoints take a base64-encoded PNG. These turn a picked file
 * or an already-rendered generation result into that form, and let a returned data URL be shown.
 */

/** Read a user-picked file as a base64 data URL (``data:image/png;base64,...``). */
export function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error ?? new Error("failed to read file"));
    reader.readAsDataURL(file);
  });
}

/** Fetch an image URL (e.g. a generation result) and re-encode it as a PNG data URL via a canvas. */
export function imageUrlToBase64(url: string): Promise<string> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.crossOrigin = "anonymous";
    image.onload = () => {
      const canvas = document.createElement("canvas");
      canvas.width = image.naturalWidth;
      canvas.height = image.naturalHeight;
      const context = canvas.getContext("2d");
      if (!context) {
        reject(new Error("canvas 2d context unavailable"));
        return;
      }
      context.drawImage(image, 0, 0);
      resolve(canvas.toDataURL("image/png"));
    };
    image.onerror = () => reject(new Error(`failed to load image: ${url}`));
    image.src = url;
  });
}

/** Strip the ``data:...;base64,`` prefix if present — the backend accepts either form. */
export function stripDataUrl(data: string): string {
  const comma = data.indexOf(",");
  return data.startsWith("data:") && comma >= 0 ? data.slice(comma + 1) : data;
}

export interface DecodedImage {
  data: Uint8ClampedArray;
  width: number;
  height: number;
}

/** Decode a data URL (or any image src) into raw RGBA pixels for the editor. */
export function decodeImage(src: string): Promise<DecodedImage> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.crossOrigin = "anonymous";
    image.onload = () => {
      const canvas = document.createElement("canvas");
      canvas.width = image.naturalWidth;
      canvas.height = image.naturalHeight;
      const context = canvas.getContext("2d");
      if (!context) {
        reject(new Error("canvas 2d context unavailable"));
        return;
      }
      context.drawImage(image, 0, 0);
      const { data } = context.getImageData(0, 0, canvas.width, canvas.height);
      resolve({ data, width: canvas.width, height: canvas.height });
    };
    image.onerror = () => reject(new Error("failed to decode image"));
    image.src = src;
  });
}
