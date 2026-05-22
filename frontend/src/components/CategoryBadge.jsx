import { useEffect, useState } from "react";
import { getCategoryMetadata } from "../api/client";

export default function CategoryBadge({ category }) {
  const [meta, setMeta] = useState(null);

  useEffect(() => {
    let cancelled = false;
    getCategoryMetadata().then((data) => {
      if (!cancelled) setMeta(data[category] || null);
    });
    return () => {
      cancelled = true;
    };
  }, [category]);

  const color = meta?.color || "#9CA3AF";
  const name = meta?.display_name || category || "—";
  const protectedFlag = meta?.protected;

  return (
    <span
      className="category-badge"
      style={{
        backgroundColor: `${color}22`,
        borderColor: `${color}55`,
        color: color,
      }}
      title={category}
    >
      {name}
      {protectedFlag ? <span className="protected">🔒</span> : null}
    </span>
  );
}
