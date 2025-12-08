import { useState, useMemo } from "react";
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useSensor,
  useSensors,
  rectIntersection,
} from "@dnd-kit/core";
import type { DragEndEvent, DragStartEvent } from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  verticalListSortingStrategy,
  useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import "./DragDropDemo.css";

// -----------------------------
// Types
// -----------------------------
export type RouteItem = {
  id: string;
  name: string;
  address: string;
  contact: string;
  priority: number;
  raw: Record<string, any>;
};

export type CardData = {
  id: string;
  title: string;
  items: RouteItem[];
};

type Props = {
  filename: string;
  columns: string[];
  groups: Record<string, any>[][];
};

// -----------------------------
// Sortable Item
// -----------------------------
function SortableItem({ item }: { item: RouteItem }) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: item.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      className="route-item"
    >
      <div className="item-name">{item.name}</div>
      <div className="item-details">
        <div>{item.address}</div>
        <div>{item.contact}</div>
        <div className="item-priority">Priority: {item.priority}</div>
      </div>
    </div>
  );
}

// -----------------------------
// Card Component
// -----------------------------
function Card({ card }: { card: CardData }) {
  const sortableIds =
    card.items.length > 0 ? card.items.map((item) => item.id) : [card.id];

  return (
    <div className="card-container">
      <h3 className="card-title">{card.title}</h3>
      <SortableContext
        items={sortableIds}
        strategy={verticalListSortingStrategy}
      >
        {card.items.length === 0 ? (
          <div className="empty-card-placeholder">Drop items here</div>
        ) : (
          card.items.map((item) => <SortableItem key={item.id} item={item} />)
        )}
      </SortableContext>

      <div className="card-count">{card.items.length} stops</div>
    </div>
  );
}

// -----------------------------
// Main Component
// -----------------------------
export default function DragDropDemo({ filename, columns, groups }: Props) {
  // ------------------------------------
  // Convert backend groups → RouteItem[]
  // ------------------------------------
  const initialCards: CardData[] = useMemo(() => {
    return groups.map((group, index) => ({
      id: `group-${index + 1}`,
      title: `Group ${index + 1}`,
      items: group.map((row, rowIndex) => ({
        id: `g${index}-row${rowIndex}`,
        name: row["name"] || row["Name"] || row[columns[0]] || "Unknown",
        address: row["location"] || row["Location"] || "",
        contact: row["contact"] || row["Contact"] || "",
        priority: Number(row["priority"] || row["Priority"] || rowIndex + 1),
        raw: row, // keep original row for exporting
      })),
    }));
  }, [groups, columns]);

  const [cards, setCards] = useState<CardData[]>(initialCards);
  const [activeItem, setActiveItem] = useState<RouteItem | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } })
  );

  // ------------------------------------
  // Drag Start
  // ------------------------------------
  const handleDragStart = (event: DragStartEvent) => {
    const activeId = event.active.id as string;

    for (const card of cards) {
      const item = card.items.find((i) => i.id === activeId);
      if (item) {
        setActiveItem(item);
        break;
      }
    }
  };

  // ------------------------------------
  // Drag End
  // ------------------------------------
  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveItem(null);

    if (!over || active.id === over.id) return;

    const activeId = active.id as string;
    const overId = over.id as string;

    let activeCardIndex = -1;
    let overCardIndex = -1;
    let activeItemIndex = -1;
    let overItemIndex = -1;

    cards.forEach((card, cardIdx) => {
      card.items.forEach((item, itemIdx) => {
        if (item.id === activeId) {
          activeCardIndex = cardIdx;
          activeItemIndex = itemIdx;
        }
        if (item.id === overId) {
          overCardIndex = cardIdx;
          overItemIndex = itemIdx;
        }
      });
    });

    if (activeCardIndex === -1 || overCardIndex === -1) return;

    setCards((prev) => {
      const newCards = structuredClone(prev);

      // remove
      const item = newCards[activeCardIndex].items.splice(
        activeItemIndex,
        1
      )[0];

      // insert
      newCards[overCardIndex].items.splice(overItemIndex, 0, item);

      return newCards;
    });
  };

  // ------------------------------------
  // Export JSON
  // ------------------------------------
  const handleExportJSON = () => {
    const exportData = cards.map((card) => ({
      card: card.title,
      items: card.items.map((i) => i.raw),
    }));

    const dataStr = JSON.stringify(exportData, null, 2);
    const blob = new Blob([dataStr], { type: "application/json" });
    const url = URL.createObjectURL(blob);

    const a = document.createElement("a");
    a.href = url;
    a.download = `${filename}-routes.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // ------------------------------------
  // UI
  // ------------------------------------
  return (
    <div className="demo-container">
      <div className="demo-header">
        <h1>Route Planning – Drag & Drop</h1>
        <button className="export-button" onClick={handleExportJSON}>
          Export JSON
        </button>
      </div>

      <DndContext
        sensors={sensors}
        collisionDetection={rectIntersection}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
      >
        <div className="cards-grid">
          {cards.map((card) => (
            <Card key={card.id} card={card} />
          ))}
        </div>

        <DragOverlay>
          {activeItem && (
            <div className="route-item dragging">
              <div className="item-name">{activeItem.name}</div>
              <div className="item-details">
                <div>{activeItem.address}</div>
                <div>{activeItem.contact}</div>
                <div>Priority: {activeItem.priority}</div>
              </div>
            </div>
          )}
        </DragOverlay>
      </DndContext>
    </div>
  );
}
