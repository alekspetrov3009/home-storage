import { Link } from "react-router-dom";
import { formatDate, type Item } from "../api";
import { Badge, Card, Chip } from "./ui";

export default function ItemCard({ item }: { item: Item }) {
  return (
    <Card hover className="item-card">
      <div className="item-card-title">
        <Link to={`/item/${encodeURIComponent(item.id)}`}>{item.name}</Link>
        <Badge>{item.quantity}</Badge>
      </div>
      <div className="chips-row">
        {item.category && <Chip>{item.category}</Chip>}
        {item.box_label ? (
          <Chip>{item.box_label}</Chip>
        ) : (
          <Chip>— без ящика —</Chip>
        )}
      </div>
      {item.notes && <p className="dim item-card-notes">{item.notes}</p>}
      <p className="dim num">Обновлён: {formatDate(item.updated_at)}</p>
    </Card>
  );
}
