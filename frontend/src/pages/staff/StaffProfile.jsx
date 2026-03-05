import { useAuth } from '../../context/AuthContext'
import { User, Phone, Briefcase, Calendar, IndianRupee, Award, Clock } from 'lucide-react'
import { format } from 'date-fns'

export default function StaffProfile() {
  const { user } = useAuth()

  const details = [
    { icon: User, label: 'Full Name', value: user?.full_name },
    { icon: Phone, label: 'Phone', value: user?.phone ? `+91 ${user.phone}` : null },
    { icon: Briefcase, label: 'Designation', value: user?.designation },
    {
      icon: Calendar,
      label: 'Joining Date',
      value: user?.joining_date ? format(new Date(user.joining_date), 'dd MMM yyyy') : null,
    },
    { icon: IndianRupee, label: 'Weekly Salary', value: user?.weekly_salary ? `₹${user.weekly_salary}` : null },
    { icon: Clock, label: 'Login Time', value: user?.login_time },
    { icon: Clock, label: 'Logout Time', value: user?.logout_time },
  ]

  return (
    <div className="max-w-lg mx-auto space-y-6 animate-slide-up">
      {/* Avatar Header */}
      <div className="card text-center !py-8">
        <div className="h-20 w-20 rounded-full gradient-primary flex items-center justify-center mx-auto text-white text-2xl font-bold shadow-lg shadow-primary-600/25">
          {user?.full_name?.charAt(0) || 'S'}
        </div>
        <h1 className="text-xl font-bold text-slate-800 mt-3">{user?.full_name || 'Staff Member'}</h1>
        <p className="text-sm text-slate-500 mt-0.5">{user?.designation || 'Team Member'}</p>
        <div className="inline-flex items-center gap-1.5 mt-2 px-3 py-1 rounded-full bg-emerald-50 text-emerald-700 text-xs font-semibold border border-emerald-200">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
          Active
        </div>
      </div>

      {/* Details */}
      <div className="card space-y-0 !p-0 divide-y divide-slate-100">
        {details.map(
          (item, idx) =>
            item.value && (
              <div key={idx} className="flex items-center gap-3 px-5 py-3.5">
                <div className="flex items-center justify-center h-9 w-9 rounded-xl bg-primary-50">
                  <item.icon className="h-4 w-4 text-primary-600" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-slate-400 font-medium">{item.label}</p>
                  <p className="text-sm font-semibold text-slate-700 truncate">{item.value}</p>
                </div>
              </div>
            )
        )}
      </div>

      {/* Skills */}
      {user?.skills && user.skills.length > 0 && (
        <div className="card space-y-3">
          <h3 className="text-sm font-bold text-slate-700 flex items-center gap-2">
            <Award className="h-4 w-4 text-accent-600" />
            Skills
          </h3>
          <div className="flex flex-wrap gap-2">
            {user.skills.map((skill, idx) => (
              <span
                key={idx}
                className="px-3 py-1.5 rounded-full bg-primary-50 text-primary-700 text-xs font-semibold border border-primary-100"
              >
                {skill}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Emergency Contact */}
      {user?.emergency_contact && (
        <div className="card space-y-2">
          <h3 className="text-sm font-bold text-slate-700">Emergency Contact</h3>
          <p className="text-sm text-slate-600">
            {user.emergency_contact.name} — {user.emergency_contact.phone}
          </p>
          {user.emergency_contact.relationship && (
            <p className="text-xs text-slate-400">{user.emergency_contact.relationship}</p>
          )}
        </div>
      )}
    </div>
  )
}
