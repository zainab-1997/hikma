function AppIcon({ name, size = 20, className = '' }) {
  const paths = {
    package: <><path d="m7.5 4.3 9 5.2v10.4l-9 5.2-9-5.2V9.5l9-5.2Z" /><path d="m-1.5 9.5 9 5.2 9-5.2M7.5 14.7v10.4M3 6.9l9 5.2" /></>,
    plus: <><path d="M12 5v14M5 12h14" /><path d="M4 3h16a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z" /></>,
    history: <><path d="M3 12a9 9 0 1 0 3-6.7L3 8" /><path d="M3 3v5h5M12 7v5l3 2" /></>,
    chart: <><path d="M4 20V10M10 20V4M16 20v-7M22 20H2" /></>,
    activity: <><path d="M3 12h4l2-7 4 14 2-7h6" /></>,
    menu: <><path d="M4 7h16M4 12h16M4 17h16" /></>,
    close: <><path d="m6 6 12 12M18 6 6 18" /></>,
    refresh: <><path d="M20 11a8 8 0 1 0-2.3 5.7" /><path d="M20 4v7h-7" /></>,
    message: <><path d="M21 15a4 4 0 0 1-4 4H8l-5 3 1.5-5A8 8 0 1 1 21 15Z" /></>,
    info: <><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8h.01" /></>,
    summary: <><path d="M5 4h14v16H5zM8 8h8M8 12h8M8 16h5" /></>,
    success: <><circle cx="12" cy="12" r="9" /><path d="m8 12 2.5 2.5L16.5 8" /></>,
    download: <><path d="M12 3v12m0 0 4-4m-4 4-4-4M5 21h14" /></>,
  }
  return (
    <svg className={className} width={size} height={size} viewBox={name === 'package' ? "-2 -1 20 28" : "0 0 24 24"}
      fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"
      aria-hidden="true">
      {paths[name]}
    </svg>
  )
}

export default AppIcon
