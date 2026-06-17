<template>
  <header class="app-header">
    <h1>📅 EventView</h1>
    <nav>
      <RouterLink to="/">Agenda</RouterLink>
      <RouterLink to="/kalender">Kalender</RouterLink>
    </nav>
  </header>
  <main class="container">
    <RouterView />
  </main>
</template>
