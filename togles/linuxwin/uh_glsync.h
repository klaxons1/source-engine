#ifndef UH_GLSYNC_H
#define UH_GLSYNC_H
// GL constants/types must be defined by the caller (also used by native tests).
inline bool UHGLFenceSignaled(GLenum status) {
    return status == GL_ALREADY_SIGNALED || status == GL_CONDITION_SATISFIED;
}
// Keep a real blocking wait for correctness, but do not busy-spin with timeout=0.
// Submit pending commands once, then let the driver sleep in bounded 1ms waits.
// The caller must treat GL_WAIT_FAILED as an error, not as GPU completion.
template<typename Wait>
bool UHGLWaitForFence(Wait wait) {
    GLenum status = wait(0, 0);
    if (UHGLFenceSignaled(status)) return true;
    GLbitfield flags = GL_SYNC_FLUSH_COMMANDS_BIT;
    while (status == GL_TIMEOUT_EXPIRED) {
        status = wait(flags, 1000000);
        flags = 0;
    }
    return UHGLFenceSignaled(status);
}
#endif
