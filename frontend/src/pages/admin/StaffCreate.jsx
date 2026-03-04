import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import * as usersService from '../../services/users'
import { AlertCircle, CheckCircle2, UserPlus, X, Plus } from 'lucide-react'

const designations = [
  'Master Tailor',
  'Senior Tailor',
  'Junior Tailor',
  'Embroidery Specialist',
  'Cutting Master',
  'Helper',
  'Store Manager',
  'Receptionist',
  'Other',
]

export default function StaffCreate() {
  const [role, setRole] = useState('staff')
  const [form, setForm] = useState({
    full_name: '',
    phone: '',
    pin: '',
    designation: '',
    joining_date: '',
    login_time: '09:00',
    logout_time: '18:00',
    emergency_contact_name: '',
    emergency_contact_phone: '',
    weekly_salary: '',
    skills: [],
    status: 'active',
  })
  const [skillInput, setSkillInput] = useState('')
  const [errors, setErrors] = useState({})
  const [submitting, setSubmitting] = useState(false)
  const [success, setSuccess] = useState('')
  const [apiError, setApiError] = useState('')
  const navigate = useNavigate()

  function handleChange(e) {
    const { name, value } = e.target
    setForm((prev) => ({ ...prev, [name]: value }))
    if (errors[name]) setErrors((prev) => ({ ...prev, [name]: '' }))
  }

  function addSkill() {
    const skill = skillInput.trim()
    if (skill && !form.skills.includes(skill)) {
      setForm((prev) => ({ ...prev, skills: [...prev.skills, skill] }))
    }
    setSkillInput('')
  }

  function removeSkill(skill) {
    setForm((prev) => ({ ...prev, skills: prev.skills.filter((s) => s !== skill) }))
  }

  function validate() {
    const errs = {}
    if (!form.full_name.trim()) errs.full_name = 'Full name is required'
    if (!form.phone.trim() || form.phone.replace(/\D/g, '').length !== 10)
      errs.phone = 'Valid 10-digit phone is required'
    if (!form.pin.trim() || form.pin.length < 4) errs.pin = 'PIN must be at least 4 digits'

    if (role === 'staff') {
      if (!form.designation) errs.designation = 'Designation is required'
      if (!form.joining_date) errs.joining_date = 'Joining date is required'
      if (!form.login_time) errs.login_time = 'Login time is required'
      if (!form.logout_time) errs.logout_time = 'Logout time is required'
      if (!form.weekly_salary || parseFloat(form.weekly_salary) <= 0)
        errs.weekly_salary = 'Valid salary is required'
    }
    setErrors(errs)
    return Object.keys(errs).length === 0
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!validate()) return
    setSubmitting(true)
    setApiError('')
    try {
      const payload = {
        full_name: form.full_name.trim(),
        phone: form.phone.replace(/\D/g, ''),
        pin: form.pin,
      }

      if (role === 'staff') {
        Object.assign(payload, {
          designation: form.designation,
          joining_date: form.joining_date,
          login_time: form.login_time,
          logout_time: form.logout_time,
          weekly_salary: parseFloat(form.weekly_salary),
          skills: form.skills,
          status: form.status,
        })
        if (form.emergency_contact_name) {
          payload.emergency_contact = {
            name: form.emergency_contact_name,
            phone: form.emergency_contact_phone,
          }
        }
        await usersService.createStaff(payload)
      } else {
        await usersService.createAdmin(payload)
      }

      setSuccess(`${role === 'staff' ? 'Staff' : 'Admin'} created successfully!`)
      setTimeout(() => navigate('/admin/staff'), 1500)
    } catch (err) {
      setApiError(err.response?.data?.error || `Failed to create ${role}`)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6 animate-slide-up">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Add New Member</h1>
          <p className="text-sm text-slate-500 mt-0.5">Create a new team member account</p>
        </div>
      </div>

      {success && (
        <div className="flex items-center gap-2 text-success-700 text-sm bg-success-50 rounded-xl px-4 py-3 border border-emerald-100">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          {success}
        </div>
      )}

      {apiError && (
        <div className="flex items-center gap-2 text-danger-600 text-sm bg-danger-50 rounded-xl px-4 py-3 border border-danger-100">
          <AlertCircle className="h-4 w-4 shrink-0" />
          {apiError}
        </div>
      )}

      {/* Role Toggle */}
      <div className="card">
        <label className="label">Account Type</label>
        <div className="flex gap-3">
          {['staff', 'admin'].map((r) => (
            <button
              key={r}
              type="button"
              onClick={() => setRole(r)}
              className={`flex-1 py-3 rounded-xl text-sm font-semibold border-2 transition-all ${
                role === r
                  ? 'border-primary-600 bg-primary-50 text-primary-700'
                  : 'border-slate-200 bg-white text-slate-500 hover:border-slate-300'
              }`}
            >
              {r === 'staff' ? 'Staff Member' : 'Admin'}
            </button>
          ))}
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Basic Info */}
        <div className="card space-y-4">
          <h2 className="text-sm font-bold text-slate-700">Basic Information</h2>
          <div className="grid sm:grid-cols-2 gap-4">
            <div>
              <label className="label">Full Name *</label>
              <input
                type="text"
                name="full_name"
                value={form.full_name}
                onChange={handleChange}
                placeholder="Enter full name"
                className="input-field"
              />
              {errors.full_name && (
                <p className="text-xs text-danger-600 mt-1">{errors.full_name}</p>
              )}
            </div>
            <div>
              <label className="label">Phone Number *</label>
              <input
                type="tel"
                name="phone"
                value={form.phone}
                onChange={handleChange}
                placeholder="10-digit mobile number"
                className="input-field"
                inputMode="numeric"
                maxLength={10}
              />
              {errors.phone && <p className="text-xs text-danger-600 mt-1">{errors.phone}</p>}
            </div>
          </div>
          <div className="sm:w-1/2">
            <label className="label">Default PIN *</label>
            <input
              type="password"
              name="pin"
              value={form.pin}
              onChange={handleChange}
              placeholder="4-6 digit PIN"
              className="input-field"
              inputMode="numeric"
              maxLength={6}
            />
            {errors.pin && <p className="text-xs text-danger-600 mt-1">{errors.pin}</p>}
          </div>
        </div>

        {/* Staff-specific fields */}
        {role === 'staff' && (
          <>
            <div className="card space-y-4">
              <h2 className="text-sm font-bold text-slate-700">Work Details</h2>
              <div className="grid sm:grid-cols-2 gap-4">
                <div>
                  <label className="label">Designation *</label>
                  <select
                    name="designation"
                    value={form.designation}
                    onChange={handleChange}
                    className="input-field"
                  >
                    <option value="">Select designation</option>
                    {designations.map((d) => (
                      <option key={d} value={d}>
                        {d}
                      </option>
                    ))}
                  </select>
                  {errors.designation && (
                    <p className="text-xs text-danger-600 mt-1">{errors.designation}</p>
                  )}
                </div>
                <div>
                  <label className="label">Joining Date *</label>
                  <input
                    type="date"
                    name="joining_date"
                    value={form.joining_date}
                    onChange={handleChange}
                    className="input-field"
                  />
                  {errors.joining_date && (
                    <p className="text-xs text-danger-600 mt-1">{errors.joining_date}</p>
                  )}
                </div>
                <div>
                  <label className="label">Login Time *</label>
                  <input
                    type="time"
                    name="login_time"
                    value={form.login_time}
                    onChange={handleChange}
                    className="input-field"
                  />
                  {errors.login_time && (
                    <p className="text-xs text-danger-600 mt-1">{errors.login_time}</p>
                  )}
                </div>
                <div>
                  <label className="label">Logout Time *</label>
                  <input
                    type="time"
                    name="logout_time"
                    value={form.logout_time}
                    onChange={handleChange}
                    className="input-field"
                  />
                  {errors.logout_time && (
                    <p className="text-xs text-danger-600 mt-1">{errors.logout_time}</p>
                  )}
                </div>
              </div>
            </div>

            <div className="card space-y-4">
              <h2 className="text-sm font-bold text-slate-700">Compensation & Contact</h2>
              <div className="grid sm:grid-cols-2 gap-4">
                <div>
                  <label className="label">Weekly Salary (₹) *</label>
                  <input
                    type="number"
                    name="weekly_salary"
                    value={form.weekly_salary}
                    onChange={handleChange}
                    placeholder="0.00"
                    className="input-field"
                    min="0"
                    step="any"
                  />
                  {errors.weekly_salary && (
                    <p className="text-xs text-danger-600 mt-1">{errors.weekly_salary}</p>
                  )}
                </div>
                <div>
                  <label className="label">Status</label>
                  <select
                    name="status"
                    value={form.status}
                    onChange={handleChange}
                    className="input-field"
                  >
                    <option value="active">Active</option>
                    <option value="inactive">Inactive</option>
                  </select>
                </div>
                <div>
                  <label className="label">Emergency Contact Name</label>
                  <input
                    type="text"
                    name="emergency_contact_name"
                    value={form.emergency_contact_name}
                    onChange={handleChange}
                    placeholder="Contact name"
                    className="input-field"
                  />
                </div>
                <div>
                  <label className="label">Emergency Contact Phone</label>
                  <input
                    type="tel"
                    name="emergency_contact_phone"
                    value={form.emergency_contact_phone}
                    onChange={handleChange}
                    placeholder="Contact phone"
                    className="input-field"
                    inputMode="numeric"
                  />
                </div>
              </div>

              {/* Skills */}
              <div>
                <label className="label">Skills</label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={skillInput}
                    onChange={(e) => setSkillInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault()
                        addSkill()
                      }
                    }}
                    placeholder="Add a skill..."
                    className="input-field"
                  />
                  <button type="button" onClick={addSkill} className="btn-secondary !px-3">
                    <Plus className="h-4 w-4" />
                  </button>
                </div>
                {form.skills.length > 0 && (
                  <div className="flex flex-wrap gap-2 mt-2">
                    {form.skills.map((skill) => (
                      <span
                        key={skill}
                        className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-primary-50 text-primary-700 text-xs font-semibold"
                      >
                        {skill}
                        <button
                          type="button"
                          onClick={() => removeSkill(skill)}
                          className="hover:text-danger-600"
                        >
                          <X className="h-3 w-3" />
                        </button>
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </>
        )}

        {/* Submit */}
        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={() => navigate('/admin/staff')}
            className="btn-secondary"
          >
            Cancel
          </button>
          <button type="submit" disabled={submitting} className="btn-primary">
            {submitting ? (
              <div className="h-4 w-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <UserPlus className="h-4 w-4" />
            )}
            {submitting ? 'Creating...' : `Create ${role === 'staff' ? 'Staff' : 'Admin'}`}
          </button>
        </div>
      </form>
    </div>
  )
}
