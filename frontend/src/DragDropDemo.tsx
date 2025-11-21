import { useState } from "react";
import {
  DndContext,
  DragOverlay,
  closestCorners,
  PointerSensor,
  useSensor,
  useSensors,
  useDroppable,
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
import { generateMockData } from "./mockData";
import type { CardData, RouteItem } from "./mockData";
import "./DragDropDemo.css";

// Sortable Item Component
function SortableItem({ item }: { item: RouteItem }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: item.id });

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

// Card Component
function Card({ card }: { card: CardData }) {
  const { setNodeRef, isOver } = useDroppable({
    id: card.id,
  });

  // Ensure we have at least the card ID for droppable
  const sortableIds = card.items.length > 0
    ? card.items.map((item) => item.id)
    : [card.id];

  return (
    <div className="card-container">
      <h3 className="card-title">{card.title}</h3>
      <div
        ref={setNodeRef}
        className={`card-items ${isOver ? 'drag-over' : ''}`}
      >
        <SortableContext
          items={sortableIds}
          strategy={verticalListSortingStrategy}
        >
          {card.items.length === 0 ? (
            <div className="empty-card-placeholder">Drop items here</div>
          ) : (
            card.items.map((item) => (
              <SortableItem key={item.id} item={item} />
            ))
          )}
        </SortableContext>
      </div>
      <div className="card-count">{card.items.length} stops</div>
    </div>
  );
}

// Main Component
export default function DragDropDemo() {
  const [cards, setCards] = useState<CardData[]>(() => generateMockData());
  const [activeItem, setActiveItem] = useState<RouteItem | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    })
  );

  const handleDragStart = (event: DragStartEvent) => {
    const { active } = event;
    const activeId = active.id as string;

    // Find the active item
    for (const card of cards) {
      const item = card.items.find((i) => i.id === activeId);
      if (item) {
        setActiveItem(item);
        break;
      }
    }
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveItem(null);

    if (!over || active.id === over.id) {
      return;
    }

    const activeId = active.id as string;
    const overId = over.id as string;

    // Find which cards contain the active and over items
    let activeCardIndex = -1;
    let overCardIndex = -1;
    let activeItemIndex = -1;
    let overItemIndex = -1;
    let isOverCard = false;

    cards.forEach((card, cardIdx) => {
      // Check if overId is a card ID (for empty cards)
      if (card.id === overId) {
        overCardIndex = cardIdx;
        overItemIndex = 0; // Add to the beginning of empty card
        isOverCard = true;
      }

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

    if (activeCardIndex === -1 || overCardIndex === -1) {
      return;
    }

    setCards((prevCards) => {
      const newCards = [...prevCards];

      // Same card - just reorder (but not if dropping on the card itself when it's empty)
      if (activeCardIndex === overCardIndex && !isOverCard) {
        newCards[activeCardIndex] = {
          ...newCards[activeCardIndex],
          items: arrayMove(
            newCards[activeCardIndex].items,
            activeItemIndex,
            overItemIndex
          ),
        };
      } else {
        // Different cards OR dropping on empty card - move item from one to another
        const activeItem = newCards[activeCardIndex].items[activeItemIndex];

        // Remove from source
        newCards[activeCardIndex] = {
          ...newCards[activeCardIndex],
          items: newCards[activeCardIndex].items.filter((_, idx) => idx !== activeItemIndex),
        };

        // Add to destination
        const newItems = [...newCards[overCardIndex].items];
        newItems.splice(overItemIndex, 0, activeItem);
        newCards[overCardIndex] = {
          ...newCards[overCardIndex],
          items: newItems,
        };
      }

      return newCards;
    });
  };

  const handleExportJSON = () => {
    const dataStr = JSON.stringify(cards, null, 2);
    const dataBlob = new Blob([dataStr], { type: "application/json" });
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `routes-${new Date().toISOString().split("T")[0]}.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="demo-container">
      <div className="demo-header">
        <h1>Route Planning - Drag & Drop Demo</h1>
        <button className="export-button" onClick={handleExportJSON}>
          Export to JSON
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
          {activeItem ? (
            <div className="route-item dragging">
              <div className="item-name">{activeItem.name}</div>
              <div className="item-details">
                <div>{activeItem.address}</div>
                <div>{activeItem.contact}</div>
                <div className="item-priority">Priority: {activeItem.priority}</div>
              </div>
            </div>
          ) : null}
        </DragOverlay>
      </DndContext>
    </div>
  );
}
