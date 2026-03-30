import { reactive } from "vue";

export type ToastVariant = "info" | "success" | "error";

export type ToastOptions = {
  description?: string;
  duration?: number;
};

export type ToastItem = {
  id: number;
  title: string;
  description?: string;
  duration: number;
  variant: ToastVariant;
  timeoutId?: ReturnType<typeof setTimeout>;
};

const DEFAULT_DURATION = 3000;
const MAX_TOASTS = 5;

const state = reactive({
  items: [] as ToastItem[],
  defaultDuration: DEFAULT_DURATION,
});

let nextToastId = 1;

const removeToast = (id: number) => {
  const index = state.items.findIndex((item) => item.id === id);
  if (index === -1) {
    return;
  }

  const [toastItem] = state.items.splice(index, 1);
  if (toastItem.timeoutId) {
    clearTimeout(toastItem.timeoutId);
  }
};

const scheduleRemoval = (id: number, duration: number) => {
  if (typeof window === "undefined" || duration <= 0) {
    return undefined;
  }

  return window.setTimeout(() => {
    removeToast(id);
  }, duration);
};

const createToast = (
  variant: ToastVariant,
  title: string,
  options: ToastOptions = {},
) => {
  const id = nextToastId++;
  const duration = options.duration ?? state.defaultDuration;
  const toastItem: ToastItem = {
    id,
    title,
    description: options.description,
    duration,
    variant,
  };

  if (state.items.length >= MAX_TOASTS) {
    removeToast(state.items[0].id);
  }

  state.items.push(toastItem);
  toastItem.timeoutId = scheduleRemoval(id, duration);
  return id;
};

type ToastHandler = ((title: string, options?: ToastOptions) => number) & {
  success: (title: string, options?: ToastOptions) => number;
  error: (title: string, options?: ToastOptions) => number;
  dismiss: (id?: number) => void;
};

const toastHandler = ((title: string, options?: ToastOptions) =>
  createToast("info", title, options)) as ToastHandler;

toastHandler.success = (title: string, options?: ToastOptions) =>
  createToast("success", title, options);

toastHandler.error = (title: string, options?: ToastOptions) =>
  createToast("error", title, options);

toastHandler.dismiss = (id?: number) => {
  if (typeof id === "number") {
    removeToast(id);
    return;
  }

  while (state.items.length) {
    removeToast(state.items[0].id);
  }
};

export const setToastDefaults = (options: { duration?: number }) => {
  if (typeof options.duration === "number") {
    state.defaultDuration = options.duration;
  }
};

export const dismissToast = removeToast;
export const toastState = state;
export const toast = toastHandler;
