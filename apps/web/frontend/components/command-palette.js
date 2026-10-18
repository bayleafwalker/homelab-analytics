"use client";

import React, { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import Link from "next/link";

import { filterPaletteEntries } from "../lib/nav-model";

function isTypingTarget(target) {
  if (!target || !(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || target.isContentEditable;
}

// Jump-to palette over the canonical nav registry. Opens with Ctrl/Cmd+K or
// "/" outside a text field. Options are real links, so Enter follows the
// highlighted link and middle-click / open-in-new-tab keep working.
export function CommandPalette({ entries, currentPath }) {
  const dialogRef = useRef(null);
  const inputRef = useRef(null);
  const listRef = useRef(null);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const [shortcutLabel, setShortcutLabel] = useState("Ctrl K");
  // Options render only while open, so the closed palette adds no duplicate
  // link text to the page.
  const [isOpen, setIsOpen] = useState(false);
  const baseId = useId();
  const listId = `${baseId}-list`;

  const results = useMemo(() => filterPaletteEntries(entries, query), [entries, query]);

  const open = useCallback(() => {
    const dialog = dialogRef.current;
    if (!dialog || dialog.open) return;
    setQuery("");
    setActiveIndex(0);
    setIsOpen(true);
    dialog.showModal();
    inputRef.current?.focus();
  }, []);

  const close = useCallback(() => {
    dialogRef.current?.close();
  }, []);

  useEffect(() => {
    function onKeyDown(event) {
      const isShortcut = (event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k";
      const isSlash = event.key === "/" && !event.metaKey && !event.ctrlKey && !isTypingTarget(event.target);
      if (isShortcut || isSlash) {
        event.preventDefault();
        if (dialogRef.current?.open) {
          close();
        } else {
          open();
        }
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, close]);

  useEffect(() => {
    setActiveIndex(0);
  }, [query]);

  useEffect(() => {
    if (/Mac|iPhone|iPad/.test(window.navigator.platform || "")) setShortcutLabel("⌘K");
  }, []);

  useEffect(() => {
    const node = listRef.current?.querySelector(`[data-index="${activeIndex}"]`);
    node?.scrollIntoView?.({ block: "nearest" });
  }, [activeIndex]);

  function onInputKeyDown(event) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((index) => (results.length ? (index + 1) % results.length : 0));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((index) => (results.length ? (index - 1 + results.length) % results.length : 0));
    } else if (event.key === "Enter") {
      event.preventDefault();
      listRef.current?.querySelector(`[data-index="${activeIndex}"]`)?.click();
    }
  }

  const activeId = results.length ? `${baseId}-opt-${activeIndex}` : undefined;
  let lastSection = null;

  return (
    <>
      <button type="button" className="paletteTrigger" onClick={open} aria-haspopup="dialog">
        <span>Jump to a page</span>
        <kbd className="paletteKbd">{shortcutLabel}</kbd>
      </button>
      <dialog
        ref={dialogRef}
        className="palette"
        aria-label="Jump to a page"
        onClose={() => setIsOpen(false)}
        onClick={(event) => {
          if (event.target === dialogRef.current) close();
        }}
      >
        <div className="paletteInner">
          <input
            ref={inputRef}
            className="paletteInput"
            type="text"
            role="combobox"
            aria-expanded="true"
            aria-controls={listId}
            aria-activedescendant={activeId}
            aria-autocomplete="list"
            aria-label="Search pages"
            placeholder="Search pages"
            autoComplete="off"
            spellCheck={false}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={onInputKeyDown}
          />
          <ul ref={listRef} id={listId} role="listbox" aria-label="Pages" className="paletteList">
            {(isOpen ? results : []).map((entry, index) => {
              const showSection = !query && entry.section !== lastSection;
              lastSection = entry.section;
              return (
                <li key={entry.href} role="presentation">
                  {showSection ? (
                    <div className="paletteSection" aria-hidden="true">
                      {entry.section}
                    </div>
                  ) : null}
                  <Link
                    id={`${baseId}-opt-${index}`}
                    data-index={index}
                    role="option"
                    aria-selected={index === activeIndex}
                    href={entry.href}
                    className="paletteOption"
                    onMouseMove={() => setActiveIndex(index)}
                    onClick={close}
                  >
                    <span>{entry.label}</span>
                    {entry.href === currentPath ? <span className="paletteHere">You are here</span> : null}
                  </Link>
                </li>
              );
            })}
          </ul>
          {isOpen && results.length === 0 ? (
            <p className="paletteEmpty">No page matches “{query}”. Try a shorter word.</p>
          ) : null}
          <p className="paletteHint">
            Arrow keys to move, Enter to open, Esc to close.
          </p>
        </div>
      </dialog>
    </>
  );
}
