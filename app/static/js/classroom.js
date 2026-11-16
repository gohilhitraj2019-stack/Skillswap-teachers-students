// Skill Swap Classroom: WebRTC Peer-to-Peer Video & Realtime Chat / Doubt Solving
document.addEventListener('DOMContentLoaded', () => {
  const roomId = document.getElementById('classroom-room-id')?.value;
  const currentUserId = document.getElementById('current-user-id')?.value;
  const currentUserName = document.getElementById('current-user-name')?.value;
  const userRole = document.getElementById('user-role-in-class')?.value;

  if (!roomId) return;

  // Initialize Socket.IO
  const socket = io();

  // WebRTC Variables
  let localStream = null;
  let peerConnection = null;
  let isMuted = false;
  let isVideoOff = false;
  let isScreenSharing = false;

  const rtcConfig = {
    iceServers: [
      { urls: 'stun:stun.l.google.com:19302' },
      { urls: 'stun:stun1.l.google.com:19302' }
    ]
  };

  const localVideo = document.getElementById('local-video');
  const remoteVideo = document.getElementById('remote-video');
  const remotePlaceholder = document.getElementById('remote-placeholder');

  // Media Controls Elements
  const btnToggleMic = document.getElementById('btn-toggle-mic');
  const btnToggleCam = document.getElementById('btn-toggle-cam');
  const btnShareScreen = document.getElementById('btn-share-screen');

  // Initialize Local Media Stream
  async function initLocalStream() {
    try {
      localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
      if (localVideo) {
        localVideo.srcObject = localStream;
      }
    } catch (err) {
      console.warn("Camera/Microphone access not granted or unavailable:", err.message);
      const mediaAlert = document.getElementById('media-warning-alert');
      if (mediaAlert) {
        mediaAlert.classList.remove('d-none');
      }
    }
  }

  // Create WebRTC Peer Connection
  function createPeerConnection() {
    peerConnection = new RTCPeerConnection(rtcConfig);

    // Add local tracks to peer connection
    if (localStream) {
      localStream.getTracks().forEach((track) => {
        peerConnection.addTrack(track, localStream);
      });
    }

    // Handle remote tracks
    peerConnection.ontrack = (event) => {
      if (remoteVideo && event.streams[0]) {
        remoteVideo.srcObject = event.streams[0];
        if (remotePlaceholder) remotePlaceholder.classList.add('d-none');
        remoteVideo.classList.remove('d-none');
      }
    };

    // Handle ICE candidates
    peerConnection.onicecandidate = (event) => {
      if (event.candidate) {
        socket.emit('webrtc_ice_candidate', {
          room_id: roomId,
          candidate: event.candidate
        });
      }
    };

    return peerConnection;
  }

  // Socket.IO Room Joining
  socket.emit('join_classroom', { room_id: roomId });

  // When another user joins, create an offer
  socket.on('user_joined', async (data) => {
    appendSystemNotice(data.message);
    if (!peerConnection) createPeerConnection();

    try {
      const offer = await peerConnection.createOffer();
      await peerConnection.setLocalDescription(offer);
      socket.emit('webrtc_offer', {
        room_id: roomId,
        offer: offer
      });
    } catch (err) {
      console.error("Error creating WebRTC offer:", err);
    }
  });

  // When receiving an offer
  socket.on('webrtc_offer', async (data) => {
    if (!peerConnection) createPeerConnection();
    try {
      await peerConnection.setRemoteDescription(new RTCSessionDescription(data.offer));
      const answer = await peerConnection.createAnswer();
      await peerConnection.setLocalDescription(answer);
      socket.emit('webrtc_answer', {
        room_id: roomId,
        answer: answer
      });
    } catch (err) {
      console.error("Error answering WebRTC offer:", err);
    }
  });

  // When receiving an answer
  socket.on('webrtc_answer', async (data) => {
    try {
      if (peerConnection) {
        await peerConnection.setRemoteDescription(new RTCSessionDescription(data.answer));
      }
    } catch (err) {
      console.error("Error setting remote description:", err);
    }
  });

  // When receiving an ICE candidate
  socket.on('webrtc_ice_candidate', async (data) => {
    try {
      if (peerConnection && data.candidate) {
        await peerConnection.addIceCandidate(new RTCIceCandidate(data.candidate));
      }
    } catch (err) {
      console.error("Error adding ICE candidate:", err);
    }
  });

  // User left
  socket.on('user_left', (data) => {
    appendSystemNotice(data.message);
    if (remoteVideo) {
      remoteVideo.srcObject = null;
      remoteVideo.classList.add('d-none');
      if (remotePlaceholder) remotePlaceholder.classList.remove('d-none');
    }
  });

  // Controls: Mic Mute / Unmute
  if (btnToggleMic) {
    btnToggleMic.addEventListener('click', () => {
      if (localStream) {
        const audioTracks = localStream.getAudioTracks();
        if (audioTracks.length > 0) {
          isMuted = !isMuted;
          audioTracks[0].enabled = !isMuted;
          btnToggleMic.innerHTML = isMuted
            ? '<i class="bi bi-mic-mute-fill text-danger"></i> Unmute'
            : '<i class="bi bi-mic-fill"></i> Mute';
          btnToggleMic.classList.toggle('btn-outline-danger', isMuted);
        }
      }
    });
  }

  // Controls: Cam On / Off
  if (btnToggleCam) {
    btnToggleCam.addEventListener('click', () => {
      if (localStream) {
        const videoTracks = localStream.getVideoTracks();
        if (videoTracks.length > 0) {
          isVideoOff = !isVideoOff;
          videoTracks[0].enabled = !isVideoOff;
          btnToggleCam.innerHTML = isVideoOff
            ? '<i class="bi bi-camera-video-off-fill text-danger"></i> Start Cam'
            : '<i class="bi bi-camera-video-fill"></i> Stop Cam';
          btnToggleCam.classList.toggle('btn-outline-danger', isVideoOff);
        }
      }
    });
  }

  // Controls: Screen Share
  if (btnShareScreen) {
    btnShareScreen.addEventListener('click', async () => {
      if (!isScreenSharing) {
        try {
          const screenStream = await navigator.mediaDevices.getDisplayMedia({ video: true });
          const screenTrack = screenStream.getVideoTracks()[0];

          if (peerConnection) {
            const sender = peerConnection.getSenders().find((s) => s.track.kind === 'video');
            if (sender) sender.replaceTrack(screenTrack);
          }

          if (localVideo) localVideo.srcObject = screenStream;
          isScreenSharing = true;
          btnShareScreen.innerHTML = '<i class="bi bi-stop-circle-fill text-danger"></i> Stop Share';

          screenTrack.onended = () => {
            stopScreenSharing();
          };
        } catch (err) {
          console.warn("Screen share cancelled:", err);
        }
      } else {
        stopScreenSharing();
      }
    });
  }

  function stopScreenSharing() {
    if (localStream && peerConnection) {
      const videoTrack = localStream.getVideoTracks()[0];
      const sender = peerConnection.getSenders().find((s) => s.track.kind === 'video');
      if (sender && videoTrack) sender.replaceTrack(videoTrack);
      if (localVideo) localVideo.srcObject = localStream;
    }
    isScreenSharing = false;
    if (btnShareScreen) {
      btnShareScreen.innerHTML = '<i class="bi bi-display"></i> Share Screen';
    }
  }

  // Live Chat and Doubt-solving Messaging
  const chatForm = document.getElementById('chat-form');
  const chatInput = document.getElementById('chat-input');
  const chatContainer = document.getElementById('chat-messages-container');
  const doubtContainer = document.getElementById('doubt-messages-container');
  const doubtForm = document.getElementById('doubt-form');
  const doubtInput = document.getElementById('doubt-input');

  // Submit regular chat message
  if (chatForm && chatInput) {
    chatForm.addEventListener('submit', (e) => {
      e.preventDefault();
      const text = chatInput.value.trim();
      if (!text) return;
      socket.emit('send_message', {
        room_id: roomId,
        message: text,
        message_type: 'chat'
      });
      chatInput.value = '';
    });
  }

  // Submit doubt message
  if (doubtForm && doubtInput) {
    doubtForm.addEventListener('submit', (e) => {
      e.preventDefault();
      const text = doubtInput.value.trim();
      if (!text) return;
      socket.emit('send_message', {
        room_id: roomId,
        message: text,
        message_type: 'doubt'
      });
      doubtInput.value = '';
    });
  }

  // Handle incoming messages
  socket.on('new_message', (msg) => {
    if (msg.message_type === 'chat') {
      appendChatMessage(msg);
    } else if (msg.message_type === 'doubt') {
      appendDoubtMessage(msg);
    }
  });

  // Handle doubt resolved event
  socket.on('doubt_resolved', (data) => {
    const doubtBadge = document.getElementById(`doubt-badge-${data.doubt_id}`);
    const resolveBtn = document.getElementById(`btn-resolve-${data.doubt_id}`);
    if (doubtBadge) {
      doubtBadge.className = 'badge bg-success';
      doubtBadge.innerHTML = '<i class="bi bi-check2-circle"></i> Resolved';
    }
    if (resolveBtn) {
      resolveBtn.remove();
    }
  });

  function appendChatMessage(msg) {
    if (!chatContainer) return;
    const isMe = msg.sender_name === currentUserName;
    const msgDiv = document.createElement('div');
    msgDiv.className = `d-flex mb-3 ${isMe ? 'justify-content-end' : 'justify-content-start'}`;
    msgDiv.innerHTML = `
      <div style="max-width: 80%;">
        <div class="small text-muted mb-1 ${isMe ? 'text-end' : ''}">${msg.sender_name} <span class="ms-1" style="font-size: 0.7rem;">${msg.created_at}</span></div>
        <div class="p-2 rounded ${isMe ? 'bg-primary text-white' : 'bg-light border text-dark'}">
          ${escapeHtml(msg.message)}
        </div>
      </div>
    `;
    chatContainer.appendChild(msgDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
  }

  function appendDoubtMessage(msg) {
    if (!doubtContainer) return;
    const item = document.createElement('div');
    item.className = 'border rounded p-3 mb-3 bg-white shadow-sm';
    item.id = `doubt-item-${msg.id}`;

    let resolveButton = '';
    if (userRole === 'teacher' && !msg.is_resolved) {
      resolveButton = `
        <button class="btn btn-sm btn-outline-success mt-2" id="btn-resolve-${msg.id}" onclick="resolveDoubt(${msg.id})">
          <i class="bi bi-check-lg"></i> Mark as Resolved
        </button>
      `;
    }

    item.innerHTML = `
      <div class="d-flex justify-content-between align-items-start mb-1">
        <span class="fw-bold">${msg.sender_name}</span>
        <span class="badge ${msg.is_resolved ? 'bg-success' : 'bg-warning text-dark'}" id="doubt-badge-${msg.id}">
          ${msg.is_resolved ? '<i class="bi bi-check2-circle"></i> Resolved' : 'Unresolved Doubt'}
        </span>
      </div>
      <p class="mb-1 text-dark">${escapeHtml(msg.message)}</p>
      <div class="d-flex justify-content-between align-items-center">
        <span class="text-muted" style="font-size: 0.75rem;">${msg.created_at}</span>
        ${resolveButton}
      </div>
    `;
    doubtContainer.appendChild(item);
    doubtContainer.scrollTop = doubtContainer.scrollHeight;
  }

  function appendSystemNotice(text) {
    if (!chatContainer) return;
    const notice = document.createElement('div');
    notice.className = 'text-center my-2';
    notice.innerHTML = `<span class="badge bg-secondary-subtle text-secondary py-1 px-3 rounded-pill">${escapeHtml(text)}</span>`;
    chatContainer.appendChild(notice);
    chatContainer.scrollTop = chatContainer.scrollHeight;
  }

  window.resolveDoubt = (doubtId) => {
    socket.emit('resolve_doubt', { doubt_id: doubtId, room_id: roomId });
  };

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.innerText = text;
    return div.innerHTML;
  }

  // Elapsed Timer
  const timerEl = document.getElementById('session-elapsed-timer');
  if (timerEl) {
    let seconds = 0;
    setInterval(() => {
      seconds++;
      const m = String(Math.floor(seconds / 60)).padStart(2, '0');
      const s = String(seconds % 60).padStart(2, '0');
      timerEl.innerText = `${m}:${s}`;
    }, 1000);
  }

  // Start media initialization
  initLocalStream();
});
