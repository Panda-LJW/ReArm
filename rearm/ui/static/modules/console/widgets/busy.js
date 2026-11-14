// 传函数可阻止重复发令；也兼容已创建的 Promise。不覆盖业务层的 aria-disabled/reason。
const pending = new WeakMap();

export function withBusy(button, operation) {
  if (!button) {
    try { return Promise.resolve(typeof operation === "function" ? operation() : operation); }
    catch (error) { return Promise.reject(error); }
  }
  if (pending.has(button)) return pending.get(button);
  const previous = button.getAttribute("aria-busy");
  const guard = event => {
    if (event.type.startsWith("key") && !["Enter", " ", "Spacebar"].includes(event.key)) return;
    event.preventDefault(); event.stopImmediatePropagation();
  };
  const events = ["click", "dblclick", "keydown", "keyup"];
  button.setAttribute("aria-busy", "true");
  events.forEach(name => button.addEventListener(name, guard, true));
  let resolve, reject;
  const work = new Promise((yes, no) => { resolve = yes; reject = no; });
  const result = work.finally(() => {
    pending.delete(button);
    events.forEach(name => button.removeEventListener(name, guard, true));
    if (previous === null) button.removeAttribute("aria-busy");
    else button.setAttribute("aria-busy", previous);
  });
  pending.set(button, result);
  try { resolve(typeof operation === "function" ? operation() : operation); }
  catch (error) { reject(error); }
  return result;
}
