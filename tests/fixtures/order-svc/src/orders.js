import { reserve } from "./inventory.js";

export function place(order) {
  return reserve(order.sku);
}
