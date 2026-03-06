import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, type CourseListItem } from '../lib/api';

function ProgressRing({ percent, size = 48 }: { percent: number; size?: number }) {
  const stroke = 4;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (percent / 100) * circumference;

  return (
    <svg width={size} height={size} className="transform -rotate-90">
      <circle
        cx={size / 2} cy={size / 2} r={radius}
        stroke="#f5e6e6" strokeWidth={stroke} fill="none"
      />
      <circle
        cx={size / 2} cy={size / 2} r={radius}
        stroke={percent === 100 ? '#4ade80' : '#d4a0a0'}
        strokeWidth={stroke} fill="none"
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        strokeLinecap="round"
        className="transition-all duration-500"
      />
      <text
        x="50%" y="50%"
        dominantBaseline="central" textAnchor="middle"
        className="text-xs font-semibold fill-gray-700"
        transform={`rotate(90, ${size / 2}, ${size / 2})`}
      >
        {percent}%
      </text>
    </svg>
  );
}

export default function Dashboard() {
  const [courses, setCourses] = useState<CourseListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [userName, setUserName] = useState('');

  useEffect(() => {
    Promise.all([api.getMyCourses(), api.me()]).then(([c, u]) => {
      setCourses(c);
      setUserName(u.name);
    }).finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--nora-pink)]" />
      </div>
    );
  }

  return (
    <div className="p-8 max-w-5xl">
      {/* Welcome banner */}
      <div className="bg-gradient-to-r from-[var(--nora-pink)] to-[var(--nora-pink-dark)] rounded-2xl p-8 mb-8 text-white">
        <h2 className="text-2xl font-light">Willkommen, {userName}</h2>
        <p className="mt-2 opacity-90">
          Hier findest du deine Kurse und alle Inhalte.
        </p>
      </div>

      {/* Courses */}
      <h3 className="text-lg font-semibold mb-4">Deine Kurse</h3>

      {courses.length === 0 ? (
        <div className="bg-white rounded-2xl p-8 text-center text-gray-500">
          Du bist noch in keinem Kurs eingeschrieben.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {courses.map((course) => (
            <Link
              key={course.id}
              to={`/course/${course.id}`}
              className="bg-white rounded-2xl overflow-hidden shadow-sm hover:shadow-md transition-shadow group"
            >
              {course.image_url ? (
                <div
                  className="h-40 bg-cover bg-center"
                  style={{ backgroundImage: `url(${course.image_url})` }}
                />
              ) : (
                <div className="h-40 bg-gradient-to-br from-[var(--nora-pink-light)] to-[var(--nora-pink)] flex items-center justify-center">
                  <span className="text-white text-xl font-light italic">{course.title}</span>
                </div>
              )}
              <div className="p-5 flex items-center justify-between">
                <div>
                  <h4 className="font-semibold text-gray-800 group-hover:text-[var(--nora-pink-dark)] transition-colors">
                    {course.title}
                  </h4>
                  <p className="text-sm text-gray-500 mt-1">
                    {course.completed_lessons} / {course.total_lessons} Lektionen
                  </p>
                </div>
                <ProgressRing percent={course.progress_percent} />
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
