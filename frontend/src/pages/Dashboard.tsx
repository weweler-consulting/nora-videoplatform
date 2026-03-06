import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, type CourseListItem } from '../lib/api';

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
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {courses.map((course) => (
            <Link
              key={course.id}
              to={`/course/${course.id}`}
              className="bg-gradient-to-r from-[var(--nora-pink)] to-[var(--nora-pink-dark)] rounded-2xl p-8 flex items-center justify-between text-white hover:shadow-lg transition-shadow group"
            >
              <div>
                <p className="text-sm opacity-80 uppercase tracking-wider">Kurs</p>
                <h4 className="text-xl font-semibold mt-1">{course.title}</h4>
                {course.description && (
                  <p className="mt-2 opacity-90 text-sm">{course.description}</p>
                )}
                <p className="text-sm opacity-70 mt-3">
                  {course.completed_lessons} / {course.total_lessons} Lektionen
                </p>
              </div>
              <div className="shrink-0 ml-6">
                <svg width="64" height="64" className="transform -rotate-90">
                  <circle cx="32" cy="32" r="27" stroke="rgba(255,255,255,0.3)" strokeWidth="5" fill="none" />
                  <circle
                    cx="32" cy="32" r="27"
                    stroke="white" strokeWidth="5" fill="none"
                    strokeDasharray={2 * Math.PI * 27}
                    strokeDashoffset={2 * Math.PI * 27 - (course.progress_percent / 100) * 2 * Math.PI * 27}
                    strokeLinecap="round"
                    className="transition-all duration-500"
                  />
                  <text
                    x="50%" y="50%"
                    dominantBaseline="central" textAnchor="middle"
                    className="text-sm font-bold fill-white"
                    transform="rotate(90, 32, 32)"
                  >
                    {course.progress_percent}%
                  </text>
                </svg>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
