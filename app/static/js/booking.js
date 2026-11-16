// Skill Swap Booking Script
document.addEventListener('DOMContentLoaded', () => {
  const dateInput = document.getElementById('booking-date');
  const slotsContainer = document.getElementById('slots-container');
  const timeSlotHidden = document.getElementById('selected-time-slot');
  const submitBtn = document.getElementById('btn-confirm-booking');
  const teacherProfileId = document.getElementById('teacher-profile-id')?.value;

  if (!dateInput || !slotsContainer || !teacherProfileId) return;

  // Set min date to today
  const today = new Date().toISOString().split('T')[0];
  dateInput.min = today;
  if (!dateInput.value) {
    dateInput.value = today;
  }

  const loadSlots = async (selectedDate) => {
    slotsContainer.innerHTML = `
      <div class="text-center py-4 text-muted">
        <div class="spinner-border spinner-border-sm text-primary mb-2" role="status"></div>
        <div>Checking teacher availability...</div>
      </div>
    `;
    timeSlotHidden.value = '';
    if (submitBtn) submitBtn.disabled = true;

    try {
      const resp = await fetch(`/booking/slots/${teacherProfileId}?date=${selectedDate}`);
      const data = await resp.json();

      if (!data.slots || data.slots.length === 0) {
        slotsContainer.innerHTML = `
          <div class="alert alert-warning mb-0 py-2">
            <i class="bi bi-calendar-x me-1"></i> No available slots for this day. The teacher may be off or fully booked.
          </div>
        `;
        return;
      }

      let html = '<div class="d-flex flex-wrap gap-2">';
      data.slots.forEach((s) => {
        if (s.available) {
          html += `
            <div class="slot-pill" data-slot="${s.label}">
              <i class="bi bi-clock me-1"></i> ${s.label}
            </div>
          `;
        } else {
          html += `
            <div class="slot-pill disabled" title="Already booked">
              <i class="bi bi-lock me-1"></i> ${s.label} (Booked)
            </div>
          `;
        }
      });
      html += '</div>';
      slotsContainer.innerHTML = html;

      // Attach click events
      document.querySelectorAll('.slot-pill:not(.disabled)').forEach((pill) => {
        pill.addEventListener('click', () => {
          document.querySelectorAll('.slot-pill').forEach((p) => p.classList.remove('selected'));
          pill.classList.add('selected');
          timeSlotHidden.value = pill.getAttribute('data-slot');
          if (submitBtn) submitBtn.disabled = false;
        });
      });
    } catch (err) {
      console.error("Error loading slots:", err);
      slotsContainer.innerHTML = `
        <div class="alert alert-danger mb-0 py-2">
          Unable to check availability slots. Please refresh.
        </div>
      `;
    }
  };

  dateInput.addEventListener('change', (e) => {
    loadSlots(e.target.value);
  });

  // Initial load
  loadSlots(dateInput.value);
});
