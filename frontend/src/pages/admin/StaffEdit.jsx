import { useState, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import * as usersService from '../../services/users'
import LoadingSpinner from '../../components/common/LoadingSpinner'
import { AlertCircle, CheckCircle2, Save, ArrowLeft, X, Plus } from 'lucide-react'

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

export default function StaffEdit() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [form, setForm] = useState(null)
  const [skillInput, setSkillInput] = useState('')
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [errors, setErrors] = useState({})
  const [success, setSuccess] = useState('')
  const [apiError, setApiError] = useState('')

  useEffect(() => {
    async function fetchStaff() {
      try {
        const data = await usersService.getStaff(id)
        const staff = data.staff || data
        setForm({
          full_name: staff.full_name || '',
          phone: staff.phone || '',
          designation: staff.designation || '',
          joining_date: staff.joining_date ? staff.joining_date.slice(0, 10) : '',
          login_time: staff.login_time || '09:00',
          logout_time: staff.logout_time || '18:00',
          emergency_contact_name: staff.emergency_contact?.name || '',
          emergency_contact_phone: staff.emergency_contact?.phone || '',
          weekly_salary: staff.weekly_salary || '',
          skills: staff.skills || [],
          status: staff.status || 'active',
        })
      } catch {
        setApiError('Failed to load staff details')
      } finally {
        setLoading(false)
      }
    }
    fetchStaff()
  }, [id])

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
    if (!form.designation) errs.designation = 'Designation is required'
    if (!form.joining_date) errs.joining_date = 'Joining date is required'
    if (!form.weekly_salary || parseFloat(form.weekly_salary) <= 0) errs.weekly_salary = 'Valid salary is required'
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
        designation: form.designation,
        joining_date: form.joining_date,
        login_time: form.login_time,
        logout_time: form.logout_time,
        weekly_salary: parseFloat(form.weekly_salary),
        skills: form.skills,
        status: form.status,
      }
      if (form.emergency_contact_name) {
        payload.emergency_contact = {
          name: form.emergency_contact_name,
          phone: form.emergency_contact_phone,
        }
      }
      await usersService.updateStaff(id, payload)
      setSuccess('Staff updated successfully!')
      setTimeout(() => navigate(`/admin/staff/${id}`), 1500)
    } catch (err) {
      setApiError(err.response?.data?.error || 'Failed to update staff')
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) return <LoadingSpinner message="Loading staff details..." />
  if (!form) {
    return (
      <div className="card text-center py-12">
        <p className="text-sm text-slate-500">Staff member not found</p>
        <button onClick={() => navigate('/admin/staff')} className="btn-primary mt-4">
          Back to Directory
        </button>
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6 animate-slide-up">
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate(-1)}
          className="p-2 rounded-xl hover:bg-slate-100 text-slate-500"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Edit Staff</h1>
          <p className="text-sm text-slate-500 mt-0.5">Update {form.full_name}&apos;s profile</p>
        </div>
      </div>

      {success && (
        <div className="flex items-center gap-2 text-success-700 text-sm bg-success-50 rounded-xl px-4 py-3">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          {success}
        </div>
      )}
      {apiError && (
        <div className="flex items-center gap-2 text-danger-600 text-sm bg-danger-50 rounded-xl px-4 py-3">
          <AlertCircle className="h-4 w-4 shrink-0" />
          {apiError}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
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
                className="input-field"
              />
              {errors.full_name && <p className="text-xs text-danger-600 mt-1">{errors.full_name}</p>}
            </div>
            <div>
              <label className="label">Phone Number</label>
              <input
                type="tel"
                value={form.phone}
                className="input-field bg-slate-50 text-slate-500 cursor-not-allowed"
                disabled
              />
              <p className="text-xs text-slate-400 mt-1">Phone number cannot be changed</p>
            </div>
          </div>
        </div>

        <div className="card space-y-4">
          <h2 className="text-sm font-bold text-slate-700">Work Details</h2>
          <div className="grid sm:grid-cols-2 gap-4">
            <div>
              <label className="label">Designation *</label>
              <select name="designation" value={form.designation} onChange={handleChange} className="input-field">
                <option value="">Select designation</option>
                {designations.map((d) => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
              {errors.designation && <p className="text-xs text-danger-600 mt-1">{errors.designation}</p>}
            </div>
            <div>
              <label className="label">Joining Date *</label>
              <input type="date" name="joining_date" value={form.joining_date} onChange={handleChange} className="input-field" />
              {errors.joining_date && <p className="text-xs text-danger-600 mt-1">{errors.joining_date}</p>}
            </div>
            <div>
              <label className="label">Login Time</label>
              <input type="time" name="login_time" value={form.login_time} onChange={handleChange} className="input-field" />
            </div>
            <div>
              <label className="label">Logout Time</label>
              <input type="time" name="logout_time" value={form.logout_time} onChange={handleChange} className="input-field" />
            </div>
          </div>
        </div>

        <div className="card space-y-4">
          <h2 className="text-sm font-bold text-slate-700">Compensation & Contact</h2>
          <div className="grid sm:grid-cols-2 gap-4">
            <div>
              <label className="label">Weekly Salary (₹) *</label>
              <input type="number" name="weekly_salary" value={form.weekly_salary} onChange={handleChange} className="input-field" min="0" step="any" />
              {errors.weekly_salary && <p className="text-xs text-danger-600 mt-1">{errors.weekly_salary}</p>}
            </div>
            <div>
              <label className="label">Status</label>
              <select name="status" value={form.status} onChange={handleChange} className="input-field">
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
              </select>
            </div>
            <div>
              <label className="label">Emergency Contact Name</label>
              <input type="text" name="emergency_contact_name" value={form.emergency_contact_name} onChange={handleChange} className="input-field" />
            </div>
            <div>
              <label className="label">Emergency Contact Phone</label>
              <input type="tel" name="emergency_contact_phone" value={form.emergency_contact_phone} onChange={handleChange} className="input-field" />
            </div>
          </div>

          <div>
            <label className="label">Skills</label>
            <div className="flex gap-2">
              <input
                type="text"
                value={skillInput}
                onChange={(e) => setSkillInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addSkill() } }}
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
                  <span key={skill} className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-primary-50 text-primary-700 text-xs font-semibold">
                    {skill}
                    <button type="button" onClick={() => removeSkill(skill)} className="hover:text-danger-600">
                      <X className="h-3 w-3" />
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="flex justify-end gap-3">
          <button type="button" onClick={() => navigate(-1)} className="btn-secondary">Cancel</button>
          <button type="submit" disabled={submitting} className="btn-primary">
            {submitting ? (
              <div className="h-4 w-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <Save className="h-4 w-4" />
            )}
            {submitting ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      </form>
    </div>
  )
}
