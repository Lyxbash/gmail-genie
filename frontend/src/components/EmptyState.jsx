export default function EmptyState({ title, message, icon = "📭" }) {
  return (
    <div className="empty-state">
      <div className="empty-state-icon" aria-hidden>
        {icon}
      </div>
      <h3>{title}</h3>
      <p>{message}</p>
    </div>
  );
}
