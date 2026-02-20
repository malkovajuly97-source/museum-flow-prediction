using System.Collections.Generic;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.XR.ARFoundation;
using UnityEngine.XR.ARSubsystems;

/// <summary>
/// По тапу/нажатию размещает AR Content на найденной AR-плоскости (стол, пол) и закрепляет через AR Anchor.
/// Нужны: AR Raycast Manager, AR Anchor Manager на этом же объекте и ссылка на AR Content.
/// </summary>
[RequireComponent(typeof(ARRaycastManager))]
[RequireComponent(typeof(ARAnchorManager))]
public class ARPlaceOnPlane : MonoBehaviour
{
    [Header("Объект для размещения")]
    [Tooltip("Родитель пола и агентов — будет перемещён в точку тапа на плоскости и привязан к якорю.")]
    public Transform contentToPlace;

    [Header("Смещение")]
    [Tooltip("Высота над плоскостью (Y в локальных единицах), чтобы пол не уходил в стол.")]
    public float heightOffset = 0.01f;

    ARRaycastManager _raycastManager;
    ARAnchorManager _anchorManager;
    ARAnchor _currentAnchor;
    bool _isPlacing;
    static readonly List<ARRaycastHit> s_Hits = new List<ARRaycastHit>();

    void Awake()
    {
        _raycastManager = GetComponent<ARRaycastManager>();
        _anchorManager = GetComponent<ARAnchorManager>();
    }

    void Update()
    {
        if (contentToPlace == null) return;
        if (_isPlacing) return;

        Vector2 screenPoint = GetScreenPoint();
        if (screenPoint == default) return;

        if (_raycastManager.Raycast(screenPoint, s_Hits, TrackableType.PlaneWithinPolygon))
        {
            if (_anchorManager == null) return;

            ARRaycastHit hit = s_Hits[0];
            Pose pose = hit.pose;
            Vector3 placePosition = pose.position + Vector3.up * heightOffset;
            Pose anchorPose = new Pose(placePosition, pose.rotation);

            if (_currentAnchor != null)
            {
                contentToPlace.SetParent(null);
                Destroy(_currentAnchor.gameObject);
                _currentAnchor = null;
            }

            _isPlacing = true;
            PlaceContentAsync(anchorPose);
        }
    }

    async void PlaceContentAsync(Pose anchorPose)
    {
        try
        {
            var result = await _anchorManager.TryAddAnchorAsync(anchorPose);
            if (result.status.IsSuccess() && result.value != null && contentToPlace != null)
            {
                _currentAnchor = result.value;
                contentToPlace.SetParent(_currentAnchor.transform);
                contentToPlace.localPosition = Vector3.zero;
                contentToPlace.localRotation = Quaternion.identity;
            }
        }
        finally
        {
            _isPlacing = false;
        }
    }

    Vector2 GetScreenPoint()
    {
#if UNITY_EDITOR
        if (Mouse.current != null && Mouse.current.leftButton.wasPressedThisFrame)
            return Mouse.current.position.ReadValue();
#else
        if (Touchscreen.current != null && Touchscreen.current.primaryTouch.press.wasPressedThisFrame)
            return Touchscreen.current.primaryTouch.position.ReadValue();
#endif
        return default;
    }
}
