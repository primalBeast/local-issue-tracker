<script lang="ts">
  import { onMount, tick } from 'svelte';
  import type { PickerItemState } from './projectClaims';
  import {
    moveMenuFocus,
    projectMenuEntries,
    rootFocusableIndexes,
    switchFocusableIndexes,
    switchProjectMenu,
    type MenuNavKey,
    type ProjectMenuActionId,
    type SwitchProjectInput,
  } from './projectMenu';

  interface Props {
    projects: SwitchProjectInput[];
    currentSlug: string;
    pickerItemState: (slug: string) => PickerItemState;
    onaction: (id: ProjectMenuActionId) => void;
    onswitch: (slug: string) => void;
    oncloseproject: () => void;
    onclose: () => void;
  }

  let {
    projects,
    currentSlug,
    pickerItemState,
    onaction,
    onswitch,
    oncloseproject,
    onclose,
  }: Props = $props();

  const entries = projectMenuEntries();
  let subEntries = $derived(switchProjectMenu(projects, currentSlug, pickerItemState));

  let menuEl = $state<HTMLDivElement | null>(null);
  let submenuEl = $state<HTMLDivElement | null>(null);
  let rootFocus = $state(0);
  let subFocus = $state(-1);
  let submenuOpen = $state(false);

  function switchIndex(): number {
    return entries.findIndex((entry) => entry.kind === 'item' && entry.submenu);
  }

  function focusRootAt(index: number) {
    rootFocus = index;
    void tick().then(() => {
      menuEl?.querySelector<HTMLElement>(`[data-root-index="${index}"]`)?.focus();
    });
  }

  function focusSubAt(index: number) {
    subFocus = index;
    void tick().then(() => {
      submenuEl?.querySelector<HTMLElement>(`[data-sub-index="${index}"]`)?.focus();
    });
  }

  function placeSubmenu() {
    const anchor = menuEl?.querySelector<HTMLElement>(`[data-root-index="${switchIndex()}"]`);
    const el = submenuEl;
    if (!anchor || !el) return;
    const rect = anchor.getBoundingClientRect();
    el.style.top = `${rect.top}px`;
    el.style.left = `${rect.right + 4}px`;
    el.style.right = 'auto';
    const width = el.getBoundingClientRect().width || el.offsetWidth;
    if (rect.right + 4 + width > window.innerWidth - 8) {
      el.style.left = `${Math.max(8, rect.left - width - 4)}px`;
    }
    const room = Math.max(80, window.innerHeight - rect.top - 8);
    el.style.maxHeight = `${Math.min(window.innerHeight, room)}px`;
  }

  function openSubmenu() {
    const index = switchIndex();
    if (index >= 0) rootFocus = index;
    submenuOpen = true;
    const first = switchFocusableIndexes(subEntries)[0];
    if (first != null) subFocus = first;
    void tick().then(() => {
      placeSubmenu();
      if (first != null) focusSubAt(first);
    });
  }

  function submenuFocused(): boolean {
    return submenuOpen && !!submenuEl?.contains(document.activeElement);
  }

  function onRootClick(index: number) {
    const entry = entries[index];
    if (!entry || entry.kind !== 'item') return;
    rootFocus = index;
    if (entry.submenu || entry.id === 'switch') {
      if (submenuOpen) submenuOpen = false;
      else openSubmenu();
      return;
    }
    onaction(entry.id);
  }

  function onRootHover(index: number) {
    const entry = entries[index];
    if (!entry || entry.kind !== 'item') return;
    rootFocus = index;
    if (entry.submenu) {
      if (!submenuOpen) {
        submenuOpen = true;
        const first = switchFocusableIndexes(subEntries)[0];
        if (first != null) subFocus = first;
        void tick().then(() => placeSubmenu());
      }
      return;
    }
    submenuOpen = false;
  }

  function activateSubIndex(index: number) {
    const entry = subEntries[index];
    if (!entry || entry.kind === 'separator') return;
    if (entry.kind === 'close') {
      oncloseproject();
      return;
    }
    if (entry.disabled) return;
    onswitch(entry.slug);
  }

  function onMenuKey(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation();
      onclose();
      return;
    }
    const inSub = submenuFocused();
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp' || e.key === 'Home' || e.key === 'End') {
      e.preventDefault();
      const key = e.key as MenuNavKey;
      if (inSub) {
        const next = moveMenuFocus(switchFocusableIndexes(subEntries), subFocus, key);
        if (next >= 0) focusSubAt(next);
      } else {
        const next = moveMenuFocus(rootFocusableIndexes(entries), rootFocus, key);
        if (next >= 0) {
          const entry = entries[next];
          if (!(entry?.kind === 'item' && entry.submenu)) submenuOpen = false;
          focusRootAt(next);
        }
      }
      return;
    }
    if (e.key === 'ArrowRight') {
      const entry = entries[rootFocus];
      if (!inSub && entry?.kind === 'item' && entry.submenu) {
        e.preventDefault();
        openSubmenu();
      }
      return;
    }
    if (e.key === 'ArrowLeft') {
      if (inSub) {
        e.preventDefault();
        submenuOpen = false;
        const index = switchIndex();
        if (index >= 0) focusRootAt(index);
      }
      return;
    }
    if (e.key === 'Enter') {
      e.preventDefault();
      if (inSub) activateSubIndex(subFocus);
      else onRootClick(rootFocus);
    }
  }

  onMount(() => {
    const first = rootFocusableIndexes(entries)[0];
    if (first != null) focusRootAt(first);
  });

  $effect(() => {
    if (!submenuOpen) return;
    const onResize = () => placeSubmenu();
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  });
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
  bind:this={menuEl}
  class="project-menu"
  id="project-menu"
  role="menu"
  aria-label="Project"
  tabindex="-1"
  onkeydown={onMenuKey}
>
  {#each entries as entry, i}
    {#if entry.kind === 'separator'}
      <div class="project-menu-sep" role="separator"></div>
    {:else}
      <button
        type="button"
        class="project-menu-item"
        role="menuitem"
        data-root-index={i}
        tabindex="-1"
        aria-haspopup={entry.submenu ? 'menu' : undefined}
        aria-expanded={entry.submenu ? submenuOpen : undefined}
        onclick={() => onRootClick(i)}
        onmouseenter={() => onRootHover(i)}
      >
        <span>{entry.label}</span>
        {#if entry.submenu}
          <span class="project-menu-caret" aria-hidden="true">▸</span>
        {/if}
      </button>
    {/if}
  {/each}
</div>

{#if submenuOpen}
  <div
    bind:this={submenuEl}
    class="project-submenu"
    role="menu"
    aria-label="Switch project"
    tabindex="-1"
    onkeydown={onMenuKey}
  >
    {#each subEntries as entry, i}
      {#if entry.kind === 'separator'}
        <div class="project-menu-sep" role="separator"></div>
      {:else if entry.kind === 'project'}
        <button
          type="button"
          class="project-menu-item"
          class:current={entry.current}
          role="menuitemradio"
          aria-checked={entry.current}
          data-sub-index={i}
          tabindex="-1"
          disabled={entry.disabled}
          title={entry.title}
          onclick={() => activateSubIndex(i)}
        >
          <span class="project-menu-check" aria-hidden="true">{entry.current ? '✓' : ''}</span>
          <span>{entry.name}</span>
        </button>
      {:else}
        <button
          type="button"
          class="project-menu-item"
          role="menuitem"
          data-sub-index={i}
          tabindex="-1"
          onclick={() => activateSubIndex(i)}
        >
          <span class="project-menu-check" aria-hidden="true"></span>
          <span>Close project</span>
        </button>
      {/if}
    {/each}
  </div>
{/if}
