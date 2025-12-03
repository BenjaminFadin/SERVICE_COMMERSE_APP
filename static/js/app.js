// Simple demo data shared across pages
const demoData = {
  barber: {
    staff: ["Aziz", "Madina", "Otabek"],
    bookings: [
      { id: 1, time: "09:30", client: "Jamshid", service: "Male haircut", staff: "Aziz", price: 80000, status: "confirmed", source: "Mobile app" },
      { id: 2, time: "10:00", client: "Timur", service: "Haircut + beard", staff: "Madina", price: 100000, status: "pending", source: "Web" },
      { id: 3, time: "11:15", client: "Ali", service: "Beard trim", staff: "Otabek", price: 60000, status: "noshow", source: "Mobile app" },
      { id: 4, time: "13:00", client: "Walk-in client", service: "Male haircut", staff: "Aziz", price: 80000, status: "pending", source: "Walk-in" }
    ]
  },
  restaurant: {
    tables: [
      { id: 10, time: "18:30", client: "Sardor", guests: 3, area: "Main hall", status: "confirmed" },
      { id: 11, time: "19:00", client: "Gulbahor", guests: 2, area: "VIP room", status: "pending" },
      { id: 12, time: "20:00", client: "Olim", guests: 6, area: "Main hall", status: "confirmed" }
    ]
  }
};

function statusBadgeClass(status) {
  switch (status) {
    case "confirmed": return "status-badge status-confirmed";
    case "pending": return "status-badge status-pending";
    case "cancelled": return "status-badge status-cancelled";
    case "noshow": return "status-badge status-noshow";
    default: return "status-badge status-pending";
  }
}

function statusLabel(status) {
  switch (status) {
    case "confirmed": return "Confirmed";
    case "pending": return "Pending";
    case "cancelled": return "Cancelled";
    case "noshow": return "No-show";
    default: return status;
  }
}

// DASHBOARD PAGE
function initDashboardPage() {
  const bizTabs = document.querySelectorAll('[data-biz-tab]');
  const bizTitle = document.getElementById('currentBizTitle');
  const bookingList = document.getElementById('bookingList');
  const searchInput = document.getElementById('searchInput');
  const staffSelect = document.getElementById('staffSelect');
  const dateInput = document.getElementById('dateInput');

  let currentBiz = 'barber';

  if (!bookingList) return; // safety

  function populateStaffOptions() {
    staffSelect.innerHTML = "";
    const defaultOpt = document.createElement('option');
    defaultOpt.value = "";
    defaultOpt.textContent = "All staff / zones";
    staffSelect.appendChild(defaultOpt);

    if (currentBiz === 'barber') {
      demoData.barber.staff.forEach(name => {
        const opt = document.createElement('option');
        opt.value = name;
        opt.textContent = name;
        staffSelect.appendChild(opt);
      });
    } else if (currentBiz === 'restaurant') {
      const areas = Array.from(new Set(demoData.restaurant.tables.map(t => t.area)));
      areas.forEach(a => {
        const opt = document.createElement('option');
        opt.value = a;
        opt.textContent = a;
        staffSelect.appendChild(opt);
      });
    }
  }

  function renderKpis() {
    const bookingsTodayEl = document.getElementById('kpiBookingsToday');
    const revenueTodayEl = document.getElementById('kpiRevenueToday');

    if (currentBiz === 'barber') {
      const b = demoData.barber.bookings;
      bookingsTodayEl.textContent = b.length;
      const revenue = b.reduce((sum, item) => sum + (item.status === "cancelled" ? 0 : item.price), 0);
      revenueTodayEl.textContent = revenue.toLocaleString('ru-RU') + " UZS";
    } else if (currentBiz === 'restaurant') {
      const t = demoData.restaurant.tables;
      bookingsTodayEl.textContent = t.length;
      const guests = t.reduce((s, item) => s + item.guests, 0);
      revenueTodayEl.textContent = guests + " guests";
    }
  }

  function renderBookings() {
    bookingList.innerHTML = "";
    const query = (searchInput.value || "").toLowerCase();
    const staffZone = staffSelect.value;

    let items = [];
    if (currentBiz === 'barber') {
      items = demoData.barber.bookings.map(b => ({
        id: b.id,
        primary: `${b.time} · ${b.service}`,
        secondary: `${b.client} · ${b.staff}`,
        price: b.price.toLocaleString('ru-RU') + " UZS",
        status: b.status,
        meta: `${b.source}`
      }));
    } else {
      items = demoData.restaurant.tables.map(t => ({
        id: t.id,
        primary: `${t.time} · Table for ${t.guests}`,
        secondary: `${t.client} · ${t.area}`,
        price: `${t.guests} guests`,
        status: t.status,
        meta: `Source: Phone`
      }));
    }

    items = items.filter(item => {
      if (query && !(item.primary + " " + item.secondary).toLowerCase().includes(query)) {
        return false;
      }
      if (staffZone) {
        if (currentBiz === 'barber' && !item.secondary.includes(staffZone)) return false;
        if (currentBiz === 'restaurant' && !item.secondary.includes(staffZone)) return false;
      }
      return true;
    });

    if (!items.length) {
      const empty = document.createElement('div');
      empty.className = "text-muted small";
      empty.textContent = "No bookings found for selected filters.";
      bookingList.appendChild(empty);
      return;
    }

    items.forEach(item => {
      const card = document.createElement('div');
      card.className = "booking-card border p-3 mb-2 bg-white shadow-sm";
      card.innerHTML = `
        <div class="d-flex justify-content-between align-items-start">
          <div>
            <div class="fw-semibold">${item.primary}</div>
            <small>${item.secondary}</small>
          </div>
          <span class="${statusBadgeClass(item.status)}">${statusLabel(item.status)}</span>
        </div>
        <div class="d-flex justify-content-between align-items-center mt-2">
          <small>${item.meta}</small>
          <div class="d-flex align-items-center gap-2">
            <span class="fw-semibold">${item.price}</span>
            <a href="confirmed_service.html?id=${item.id}" class="btn btn-sm btn-outline-secondary">Details</a>
          </div>
        </div>
      `;
      bookingList.appendChild(card);
    });
  }

  function setBiz(biz) {
    currentBiz = biz;
    bizTitle.textContent = biz === 'barber' ? "Barbershop" : "Restaurant";
    bizTabs.forEach(tab => tab.classList.toggle('active', tab.dataset.bizTab === biz));
    populateStaffOptions();
    renderKpis();
    renderBookings();
  }

  bizTabs.forEach(tab => {
    tab.addEventListener('click', () => setBiz(tab.dataset.bizTab));
  });

  // Filters
  searchInput.addEventListener('input', renderBookings);
  staffSelect.addEventListener('change', renderBookings);
  dateInput && dateInput.addEventListener('change', renderBookings);

  // Set today's date in date input
  if (dateInput) {
    const today = new Date();
    dateInput.value = today.toISOString().slice(0, 10);
  }

  setBiz('barber');
}

// PROFILE PAGE
function initProfilePage() {
  const form = document.getElementById('profileForm');
  if (!form) return;

  const STORAGE_KEY = "ebook_profile";

  // load
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const data = JSON.parse(raw);
      for (const [name, value] of Object.entries(data)) {
        const field = form.elements[name];
        if (field) field.value = value;
      }
    }
  } catch(e) {
    console.warn("Could not load profile from storage", e);
  }

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    const data = {};
    Array.from(form.elements).forEach(el => {
      if (!el.name) return;
      data[el.name] = el.value;
    });
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
      const toastEl = document.getElementById('profileToast');
      if (toastEl) {
        const toast = new bootstrap.Toast(toastEl);
        toast.show();
      } else {
        alert('Profile saved locally (demo).');
      }
    } catch(e) {
      alert('Could not save profile in this browser.');
    }
  });
}

// CONFIRM PAGE
function initConfirmPage() {
  const url = new URL(window.location.href);
  const id = parseInt(url.searchParams.get('id') || "1", 10);
  const titleEl = document.getElementById('confirmTitle');
  const subtitleEl = document.getElementById('confirmSubtitle');
  const detailsEl = document.getElementById('confirmDetails');

  if (!detailsEl) return;

  let booking = demoData.barber.bookings.find(b => b.id === id);
  let isRestaurant = false;

  if (!booking) {
    // maybe restaurant
    const t = demoData.restaurant.tables.find(t => t.id === id);
    if (t) {
      isRestaurant = true;
      titleEl.textContent = "Table reserved";
      subtitleEl.textContent = "Your table is booked. The restaurant is waiting for you.";
      detailsEl.innerHTML = `
        <p class="mb-1"><strong>Restaurant:</strong> Kamolon Osh Labzak</p>
        <p class="mb-1"><strong>Guest name:</strong> ${t.client}</p>
        <p class="mb-1"><strong>Guests:</strong> ${t.guests}</p>
        <p class="mb-1"><strong>Date & time:</strong> Today · ${t.time}</p>
        <p class="mb-0"><strong>Area:</strong> ${t.area}</p>
      `;
      return;
    }
  }

  if (!booking) {
    // fallback text
    titleEl.textContent = "Booking confirmed";
    subtitleEl.textContent = "Your visit is booked. The team is waiting for you.";
    detailsEl.innerHTML = "<p>We could not find booking details, but your booking is confirmed.</p>";
    return;
  }

  // barber booking
  titleEl.textContent = "Booking confirmed";
  subtitleEl.textContent = "Your visit is booked. The team is waiting for you.";

  detailsEl.innerHTML = `
    <p class="mb-1"><strong>Business:</strong> Big Bro Barbershop</p>
    <p class="mb-1"><strong>Client:</strong> ${booking.client}</p>
    <p class="mb-1"><strong>Service:</strong> ${booking.service}</p>
    <p class="mb-1"><strong>Master:</strong> ${booking.staff}</p>
    <p class="mb-1"><strong>Time:</strong> Today · ${booking.time}</p>
    <p class="mb-0"><strong>Price:</strong> ${booking.price.toLocaleString('ru-RU')} UZS</p>
  `;
}

// auto-init
document.addEventListener('DOMContentLoaded', () => {
  const page = document.body.dataset.page;
  if (page === 'dashboard') initDashboardPage();
  if (page === 'profile') initProfilePage();
  if (page === 'confirm') initConfirmPage();
});