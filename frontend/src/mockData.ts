export type RouteItem = {
  id: string;
  name: string;
  address: string;
  contact: string;
  priority: number;
};

export type CardData = {
  id: string;
  title: string;
  items: RouteItem[];
};

// Generate mock data for 20 cards with route items
export const generateMockData = (): CardData[] => {
  const cards: CardData[] = [];
  const neighborhoods = [
    "Downtown", "Westside", "Eastside", "Northridge", "Southbay",
    "Uptown", "Midtown", "Riverside", "Hillside", "Parkview",
    "Lakeside", "Sunset", "Highland", "Valley", "Bayshore",
    "Greenwood", "Fairview", "Oakmont", "Maplewood", "Pinecrest"
  ];

  for (let i = 0; i < 20; i++) {
    const items: RouteItem[] = [];
    const itemCount = Math.floor(Math.random() * 5) + 2; // 2-6 items per card

    for (let j = 0; j < itemCount; j++) {
      items.push({
        id: `item-${i}-${j}`,
        name: `Location ${String.fromCharCode(65 + j)}`,
        address: `${100 + j * 50} Main St, ${neighborhoods[i]}`,
        contact: `(555) ${Math.floor(Math.random() * 900) + 100}-${Math.floor(Math.random() * 9000) + 1000}`,
        priority: Math.floor(Math.random() * 3) + 1 // Priority 1-3
      });
    }

    cards.push({
      id: `card-${i}`,
      title: `${neighborhoods[i]} Route`,
      items
    });
  }

  return cards;
};
