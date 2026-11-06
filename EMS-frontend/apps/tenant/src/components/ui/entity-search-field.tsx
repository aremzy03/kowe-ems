"use client";

import {
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
import { cn } from "@/lib/cn";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { Input } from "./input";

export type EntitySearchOption = {
  id: string;
  label: string;
  /** Extra tokens matched by the debounced query (admission no., code, etc.). */
  keywords?: string;
};

export type EntitySearchFieldProps = {
  id?: string;
  value: string;
  onChange: (id: string) => void;
  options: EntitySearchOption[];
  placeholder?: string;
  disabled?: boolean;
  loading?: boolean;
  debounceMs?: number;
  allowClear?: boolean;
  emptyMessage?: string;
  className?: string;
  /** Cap dropdown rows after filter. */
  maxResults?: number;
};

function normalize(s: string) {
  return s.trim().toLowerCase();
}

function optionMatches(option: EntitySearchOption, query: string) {
  if (!query) return true;
  const haystack = normalize(
    `${option.label} ${option.keywords ?? ""} ${option.id}`,
  );
  return haystack.includes(query);
}

/**
 * Debounced typeahead over a local entity catalog. Filters client-side
 * (APIs do not expose search yet) and writes the selected entity id.
 */
export function EntitySearchField({
  id: idProp,
  value,
  onChange,
  options,
  placeholder = "Search…",
  disabled,
  loading,
  debounceMs = 250,
  allowClear = true,
  emptyMessage = "No matches",
  className,
  maxResults = 12,
}: EntitySearchFieldProps) {
  const reactId = useId();
  const inputId = idProp ?? reactId;
  const listboxId = `${inputId}-listbox`;

  const selected = useMemo(
    () => options.find((o) => o.id === value) ?? null,
    [options, value],
  );

  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [highlight, setHighlight] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);
  const debouncedQuery = useDebouncedValue(query, debounceMs);
  const normalizedQuery = normalize(debouncedQuery);

  const filtered = useMemo(() => {
    const matches = options.filter((o) => optionMatches(o, normalizedQuery));
    return matches.slice(0, maxResults);
  }, [options, normalizedQuery, maxResults]);

  useEffect(() => {
    if (!open) return;
    setHighlight(0);
  }, [debouncedQuery, open]);

  useEffect(() => {
    function onPointerDown(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
        setQuery("");
      }
    }
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, []);

  function selectOption(option: EntitySearchOption) {
    onChange(option.id);
    setQuery("");
    setOpen(false);
  }

  function clear() {
    onChange("");
    setQuery("");
    setOpen(false);
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setOpen(true);
      setHighlight((h) => Math.min(h + 1, Math.max(filtered.length - 1, 0)));
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      setHighlight((h) => Math.max(h - 1, 0));
      return;
    }
    if (event.key === "Enter" && open && filtered[highlight]) {
      event.preventDefault();
      selectOption(filtered[highlight]);
      return;
    }
    if (event.key === "Escape") {
      setOpen(false);
      setQuery("");
    }
  }

  const showList = open && !disabled;

  return (
    <div ref={rootRef} className={cn("relative", className)}>
      {selected && !open ? (
        <div className="flex gap-2">
          <button
            type="button"
            id={inputId}
            disabled={disabled}
            onClick={() => {
              setOpen(true);
              setQuery("");
            }}
            className={cn(
              "flex min-h-[2.5rem] w-full items-center rounded-[var(--radius-nb-sm)] border border-ink bg-paper-card px-3 py-2 text-left",
              "focus-visible:outline focus-visible:outline-[3px] focus-visible:outline-offset-[3px] focus-visible:outline-accent-1",
              disabled && "cursor-not-allowed opacity-50",
            )}
            aria-haspopup="listbox"
            aria-expanded={false}
          >
            <span className="min-w-0 flex-1 truncate">{selected.label}</span>
          </button>
          {allowClear && !disabled ? (
            <button
              type="button"
              onClick={clear}
              className="shrink-0 rounded-[var(--radius-nb-sm)] border border-ink/30 bg-paper px-2 text-sm text-ink/70 hover:border-ink hover:text-ink"
              aria-label="Clear selection"
            >
              Clear
            </button>
          ) : null}
        </div>
      ) : (
        <Input
          id={inputId}
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={showList}
          aria-controls={listboxId}
          aria-activedescendant={
            showList && filtered[highlight]
              ? `${listboxId}-opt-${filtered[highlight].id}`
              : undefined
          }
          disabled={disabled}
          placeholder={loading ? "Loading…" : placeholder}
          value={query}
          autoComplete="off"
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
        />
      )}

      {showList ? (
        <ul
          id={listboxId}
          role="listbox"
          className="absolute z-30 mt-1 max-h-60 w-full overflow-auto rounded-[var(--radius-nb-sm)] border border-ink bg-paper-card shadow-nb-sm"
        >
          {loading ? (
            <li className="px-3 py-2 text-sm text-ink/65">Loading…</li>
          ) : filtered.length === 0 ? (
            <li className="px-3 py-2 text-sm text-ink/65">{emptyMessage}</li>
          ) : (
            filtered.map((option, index) => {
              const active = index === highlight;
              return (
                <li
                  key={option.id}
                  id={`${listboxId}-opt-${option.id}`}
                  role="option"
                  aria-selected={option.id === value}
                  className={cn(
                    "cursor-pointer px-3 py-2 text-sm",
                    active ? "bg-paper-tint" : "hover:bg-paper-tint/70",
                    option.id === value && "font-semibold",
                  )}
                  onMouseEnter={() => setHighlight(index)}
                  onMouseDown={(e) => {
                    e.preventDefault();
                    selectOption(option);
                  }}
                >
                  {option.label}
                </li>
              );
            })
          )}
        </ul>
      ) : null}
    </div>
  );
}
