const Paragraph = ({
  children,
  size = "text-lg",
  color = "text-slate-900",
}: {
  children: React.ReactNode;
  size?: string;
  color?: string;
}) => <span className={`mb-3 ${size} ${color} text-justify dark:text-white`}>{children}</span>;

export default Paragraph;
