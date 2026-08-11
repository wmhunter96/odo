export default function WarningBanner({ message }: { message: string }) {
  return (
    <div className="warning-banner">
      <span className="icon">⚠️</span>
      <span>{message}</span>
    </div>
  );
}
