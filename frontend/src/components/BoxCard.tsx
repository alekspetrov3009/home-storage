import { Link } from "react-router-dom";
import { formatDate, type Box } from "../api";
import { Card, Chip } from "./ui";

export default function BoxCard({ box }: { box: Box }) {
  return (
    <Card hover className="box-card">
      <div className="box-card-title">
        <Link to={`/box?box=${encodeURIComponent(box.id)}`}>{box.name}</Link>
        <span className="box-card-count num">
          {box.unit_count} <span className="count-unit">ед. · {box.item_count} поз.</span>
        </span>
      </div>
      <div className="chips-row">
        {box.location_name ? (
          <Chip>{box.location_name}</Chip>
        ) : (
          <Chip>— без места хранения —</Chip>
        )}
      </div>
      {box.description && <p className="dim">{box.description}</p>}
      <p className="dim num">Создан: {formatDate(box.created_at)}</p>
    </Card>
  );
}
