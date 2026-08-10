import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

/**
 * Small dropdown primitive.
 *
 * The panel renders into a portal at fixed coordinates rather than as an
 * absolutely positioned child. The transaction table scrolls horizontally, and
 * `overflow-x: auto` clips descendants on *both* axes — an in-flow dropdown
 * inside a row would be cut off at the table's edge.
 *
 * `renderTrigger({ toggle, isOpen })` draws the button; `children({ close })`
 * draws the panel.
 */
export function Popover({ renderTrigger, children, align = 'left', className = '' }) {
  const [rect, setRect] = useState(null);
  const triggerRef = useRef(null);
  const panelRef = useRef(null);
  const isOpen = rect !== null;

  useEffect(() => {
    if (!isOpen) return undefined;

    const close = () => setRect(null);

    function onPointerDown(event) {
      if (triggerRef.current?.contains(event.target)) return;
      if (panelRef.current?.contains(event.target)) return;
      close();
    }
    function onKeyDown(event) {
      if (event.key === 'Escape') close();
    }

    // The panel sits at coordinates captured when it opened, so scrolling the
    // page underneath (or resizing) would strand it — dismiss rather than
    // track. Scroll events don't bubble, but a capture-phase window listener
    // still receives them for *any* scroll in the document, including the
    // panel's own internal scrolling — so that case must be excluded, or
    // scrolling the dropdown's own list closes it after the first tick.
    function onWindowScroll(event) {
      if (panelRef.current?.contains(event.target)) return;
      close();
    }

    document.addEventListener('mousedown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    window.addEventListener('scroll', onWindowScroll, true);
    window.addEventListener('resize', close);

    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
      window.removeEventListener('scroll', onWindowScroll, true);
      window.removeEventListener('resize', close);
    };
  }, [isOpen]);

  function toggle() {
    setRect(isOpen ? null : triggerRef.current.getBoundingClientRect());
  }

  const style = rect
    ? {
        top: rect.bottom + 4,
        maxHeight: Math.max(160, window.innerHeight - rect.bottom - 16),
        ...(align === 'right'
          ? { right: Math.max(8, window.innerWidth - rect.right) }
          : { left: Math.max(8, rect.left) }),
      }
    : undefined;

  return (
    <>
      <span ref={triggerRef} className="inline-flex">
        {renderTrigger({ toggle, isOpen })}
      </span>
      {isOpen &&
        createPortal(
          <div
            ref={panelRef}
            style={style}
            className={`fixed z-50 overflow-y-auto rounded-lg border border-line bg-surface-raised shadow-xl shadow-black/40 ${className}`}
          >
            {children({ close: () => setRect(null) })}
          </div>,
          document.body,
        )}
    </>
  );
}
